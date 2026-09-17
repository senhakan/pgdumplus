#!/usr/bin/env python3
"""apply_pgdumpplus.py — "pg_dumpplus" (--where=PATTERN:FILTER,
--mask=PATTERN:COLUMN:EXPR) yamasini saf PostgreSQL kaynak agacina
anchor-tabanli uygular. Destek: 13.x, 16.x-18.x.
Kullanim: python3 apply_pgdumpplus.py <src_tree>
Idempotent. Anchor bulunamazsa high-level hata; dosya yazilmaz.
Sonuc: mevcut pg_dump'a DOKUNMAZ; ayni nesnelerden ikinci binary `pg_dumpplus` uretir.
"""
import sys, os, re
import hashlib
import json
import tempfile
from pathlib import Path

PATCH_FILES = (
    "src/include/fe_utils/simple_list.h",
    "src/fe_utils/simple_list.c",
    "src/fe_utils/string_utils.c",
    "src/include/fe_utils/string_utils.h",
    "src/bin/pg_dump/pg_dump.c",
    "src/bin/pg_dump/Makefile",
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomic_write(path, data):
    path = Path(path)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=".pgdumpplus-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def rd(p):
    with open(p, encoding="utf-8") as f: return f.read()
class Fail(Exception): pass

def rep_once(s, old, new, label):
    if new in s:                       # idempotent
        return s
    n = s.count(old)
    if n != 1:
        raise Fail(f"anchor [{label}] bulundu={n} (beklenen 1)")
    return s.replace(old, new)

# ---- pg_dump.c icine enjekte edilen C kodu sablonlari (mask ozellikleri) ----
# @@FM@@ -> pg_fatal (PG14+) | fatal (PG13);  @@ARGS@@ -> expand_table... argumanlari
MASK_RESOLVE_C = r"""
	/* pg_dumpplus: --mask=PATTERN:COLUMN:EXPR desenlerini cozumle */
	if (tabledata_mask_patterns.head != NULL)
	{
		SimpleStringListCell *mcell;

		for (mcell = tabledata_mask_patterns.head; mcell; mcell = mcell->next)
		{
			char	   *pat = pg_strdup(mcell->val);
			char	   *c1 = find_unquoted_char(pat, ':');
			char	   *c2;
			char	   *col;
			char	   *expr;
			char	   *literal;
			char	   *query;
			char	   *sql_col;
			PGresult   *colres;
			bool		text_ret = false;
			SimpleStringList one = {NULL, NULL};
			SimpleOidList oids = {NULL, NULL};
			SimpleOidListCell *ocell;

			if (c1 == NULL)
				@@FM@@("missing \":COLUMN:EXPR\" part in --mask pattern \"%s\"",
					   mcell->val);
			*c1 = '\0';
			c2 = find_unquoted_char(c1 + 1, ':');
			if (c2 == NULL)
				@@FM@@("missing \":EXPR\" part in --mask pattern \"%s\"",
					   mcell->val);
			*c2 = '\0';
			col = c1 + 1;
			expr = c2 + 1;

			/* Resolve SQL identifier quoting before catalog lookup. */
			literal = PQescapeLiteral(GetConnection(fout), col, strlen(col));
			if (literal == NULL)
				@@FM@@("could not quote --mask column name");
			query = psprintf("SELECT a[1], pg_catalog.cardinality(a) "
							 "FROM (SELECT pg_catalog.parse_ident(%s) AS a) s", literal);
			PQfreemem(literal);
			colres = ExecuteSqlQuery(fout, query, PGRES_TUPLES_OK);
			if (PQntuples(colres) != 1 || strcmp(PQgetvalue(colres, 0, 1), "1") != 0)
				@@FM@@("--mask column must be a single SQL identifier");
			col = pg_strdup(PQgetvalue(colres, 0, 0));
			PQclear(colres);
			pg_free(query);
			sql_col = pg_strdup(fmtId(col));

			/*
			 * Hazir kaliplar: EXPR "tc" | "phone" | "all" ise KVKK/GDPR
			 * standartlarina gore SQL ifadesi uretilir.
			 */
			if (strcmp(expr, "tc") == 0)
			{
				expr = psprintf("CASE WHEN length(%s::text) <= 4 THEN repeat('*', length(%s::text)) "
								"ELSE left(%s::text, 2) || repeat('*', length(%s::text) - 4) || right(%s::text, 2) END",
								sql_col, sql_col, sql_col, sql_col, sql_col);
				text_ret = true;
			}
			else if (strcmp(expr, "phone") == 0)
			{
				expr = psprintf("repeat('*', greatest(length(%s::text) - 3, 0)) || right(%s::text, 3)",
								sql_col, sql_col);
				text_ret = true;
			}
			else if (strcmp(expr, "all") == 0)
			{
				expr = psprintf("repeat('*', length(%s::text))", sql_col);
				text_ret = true;
			}
			pg_free(sql_col);

			simple_string_list_append(&one, pat);
			expand_table_name_patterns(fout, &one, &oids,
									   @@ARGS@@);
			if (oids.head == NULL)
				@@FM@@("no matching tables were found for --mask pattern \"%s\"",
					   mcell->val);
			for (ocell = oids.head; ocell; ocell = ocell->next)
			{
				DumpMaskEntry *me = pg_malloc(sizeof(DumpMaskEntry));

				me->next = dump_mask_entries;
				me->relid = ocell->val;
				me->colname = pg_strdup(col);
				me->expr = pg_strdup(expr);
				me->text_ret = text_ret;
				me->skip = false;
				dump_mask_entries = me;
			}
		}
	}

"""

MASK_HELPERS_C = r"""/*
 * pg_dumpplus: Return the masking SQL expression registered for
 * (relid, colname) via --mask, or NULL.  Skipped entries count as NULL.
 */
static char *
mask_expr_for(Oid relid, const char *colname)
{
	DumpMaskEntry *me;

	for (me = dump_mask_entries; me; me = me->next)
	{
		if (!me->skip && me->relid == relid &&
			strcmp(me->colname, colname) == 0)
			return me->expr;
	}
	return NULL;
}

/*
 * pg_dumpplus: Does this table carry any (non-skipped) --mask entry?
 */
static bool
table_has_masks(TableInfo *tbinfo)
{
	DumpMaskEntry *me;

	for (me = dump_mask_entries; me; me = me->next)
		if (!me->skip && me->relid == tbinfo->dobj.catId.oid)
			return true;
	return false;
}

"""

MASK_FMT_C = r"""/*
 * pg_dumpplus: like fmtCopyColumnList, except masked columns are emitted as
 * their SQL masking expression.  Used ONLY for the COPY (SELECT ...)
 * projection; the restore-side COPY header keeps real column names.
 */
static const char *
fmtMaskedColumnList(const TableInfo *ti, PQExpBuffer buffer)
{
	int			numatts = ti->numatts;
	char	  **attnames = ti->attnames;
	bool	   *attisdropped = ti->attisdropped;
	char	   *attgenerated = ti->attgenerated;
	bool		needComma = false;
	int			i;

	appendPQExpBufferChar(buffer, '(');
	for (i = 0; i < numatts; i++)
	{
		char	   *mexpr;

		if (attisdropped[i])
			continue;
		if (attgenerated[i])
			continue;
		if (needComma)
			appendPQExpBufferStr(buffer, ", ");
		mexpr = mask_expr_for(ti->dobj.catId.oid, attnames[i]);
		appendPQExpBufferStr(buffer, mexpr ? mexpr : fmtId(attnames[i]));
		needComma = true;
	}

	if (!needComma)
		return "";						/* no undropped columns */

	appendPQExpBufferChar(buffer, ')');
	return buffer->data;
}

"""

MASK_VALIDATE_C = r"""
	/*
	 * pg_dumpplus: bu tabloya iliskin --mask kayitlarini katalogda dogrula;
	 * gecerizse skip + uyari.
	 */
	if (dump_mask_entries != NULL)
	{
		DumpMaskEntry *me;
		int			k;

		for (me = dump_mask_entries; me; me = me->next)
		{
			bool		found = false;

			if (me->skip || me->relid != tbinfo->dobj.catId.oid)
				continue;
			for (k = 0; k < tbinfo->numatts; k++)
			{
				if (strcmp(tbinfo->attnames[k], me->colname) != 0)
					continue;
				found = true;
				if (tbinfo->attisdropped[k])
				{
					me->skip = true;
					pg_log_warning("pg_dumpplus: --mask column \"%s\" of \"%s\" is dropped; mask ignored",
								   me->colname, tbinfo->dobj.name);
				}
				else if (tbinfo->attgenerated[k])
				{
					me->skip = true;
					pg_log_warning("pg_dumpplus: --mask column \"%s\" of \"%s\" is generated; mask ignored",
								   me->colname, tbinfo->dobj.name);
				}
				else if (me->text_ret &&
						 strcmp(tbinfo->atttypnames[k], "text") != 0 &&
						 strcmp(tbinfo->atttypnames[k], "bpchar") != 0 &&
						 strncmp(tbinfo->atttypnames[k], "character varying", 17) != 0)
					pg_log_warning("pg_dumpplus: --mask preset on \"%s\".\"%s\" (%s column) yields text; restore into a non-text column may fail",
								   tbinfo->dobj.name, me->colname,
								   tbinfo->atttypnames[k]);
				break;
			}
			if (!found)
			{
				me->skip = true;
				pg_log_warning("pg_dumpplus: --mask column \"%s\" not found in table \"%s\"; mask ignored",
							   me->colname, tbinfo->dobj.name);
			}
		}
	}
"""

def main(root):
    P = lambda *a: os.path.join(root, *a)
    manifest = Path(root) / ".pgdumpplus-patch.json"
    patcher_hash = digest(Path(__file__).read_bytes())
    originals = {P(name): Path(P(name)).read_bytes() for name in PATCH_FILES}
    if manifest.exists():
        state = json.loads(manifest.read_text())
        expected = {name: digest(originals[P(name)]) for name in PATCH_FILES}
        if state.get("patcher") != patcher_hash or state.get("files") != expected:
            raise Fail("patch revision or source files changed; use a clean upstream source tree")
        print("Already applied; all patched file hashes verified.")
        return
    if any(b"pg_dumpplus" in data for data in originals.values()):
        raise Fail("older or incomplete patch detected; use a clean upstream source tree")

    # Validate every anchor in memory before changing any source file.
    pending = {}
    def wr(path, content):
        pending[path] = content.encode("utf-8")

    changed = []

    # ---------- 1) fe_utils/simple_list.h ----------
    h = P("src","include","fe_utils","simple_list.h"); t = rd(h)
    t = rep_once(t,
        "\tstruct SimpleOidListCell *next;\n\tOid\t\t\tval;\n} SimpleOidListCell;",
        "\tstruct SimpleOidListCell *next;\n\tOid\t\t\tval;\n\tvoid\t   *extra_data;\t\t/* pg_dumpplus: optional payload, or NULL */\n} SimpleOidListCell;",
        "slh-struct")
    t = rep_once(t,
        "extern void simple_oid_list_append(SimpleOidList *list, Oid val);\nextern bool simple_oid_list_member(SimpleOidList *list, Oid val);",
        "extern void simple_oid_list_append(SimpleOidList *list, Oid val);\nextern void simple_oid_list_append_data(SimpleOidList *list, Oid val,\n\t\t\t\t\t\t\t\t\t\t\t\t\tvoid *extra_data);\nextern bool simple_oid_list_member(SimpleOidList *list, Oid val);\nextern bool simple_oid_list_find_data(SimpleOidList *list, Oid val,\n\t\t\t\t\t\t\t\t\t\t\t\t\t  void **extra_data);",
        "slh-protos")
    wr(h, t); changed.append(h)

    # ---------- 2) fe_utils/simple_list.c ----------
    c = P("src","fe_utils","simple_list.c"); t = rd(c)
    t = rep_once(t,
"""void
simple_oid_list_append(SimpleOidList *list, Oid val)
{
\tSimpleOidListCell *cell;

\tcell = (SimpleOidListCell *) pg_malloc(sizeof(SimpleOidListCell));
\tcell->next = NULL;
\tcell->val = val;

\tif (list->tail)
\t\tlist->tail->next = cell;
\telse
\t\tlist->head = cell;
\tlist->tail = cell;
}

/*
 * Is OID present in the list?
 */
bool
simple_oid_list_member(SimpleOidList *list, Oid val)
{
\tSimpleOidListCell *cell;

\tfor (cell = list->head; cell; cell = cell->next)
\t{
\t\tif (cell->val == val)
\t\t\treturn true;
\t}
\treturn false;
}""",
"""void
simple_oid_list_append(SimpleOidList *list, Oid val)
{
\tsimple_oid_list_append_data(list, val, NULL);
}

/*
 * pg_dumpplus: Append an OID to the list, along with extra pointer-sized data.
 */
void
simple_oid_list_append_data(SimpleOidList *list, Oid val, void *extra_data)
{
\tSimpleOidListCell *cell;

\tcell = (SimpleOidListCell *) pg_malloc(sizeof(SimpleOidListCell));
\tcell->next = NULL;
\tcell->val = val;
\tcell->extra_data = extra_data;

\tif (list->tail)
\t\tlist->tail->next = cell;
\telse
\t\tlist->head = cell;
\tlist->tail = cell;
}

/*
 * Is OID present in the list?
 */
bool
simple_oid_list_member(SimpleOidList *list, Oid val)
{
\treturn simple_oid_list_find_data(list, val, NULL);
}

/*
 * pg_dumpplus: Is OID present?  If so and extra_data != NULL, store the
 * cell's associated extra data through *extra_data.
 */
bool
simple_oid_list_find_data(SimpleOidList *list, Oid val, void **extra_data)
{
\tSimpleOidListCell *cell;

\tfor (cell = list->head; cell; cell = cell->next)
\t{
\t\tif (cell->val == val)
\t\t{
\t\t\tif (extra_data)
\t\t\t\t*extra_data = cell->extra_data;
\t\t\treturn true;
\t\t}
\t}
\treturn false;
}""", "slc")
    wr(c, t); changed.append(c)

    # ---------- 3) fe_utils/string_utils.[ch] ----------
    su = P("src","fe_utils","string_utils.c"); t = rd(su)
    if "find_unquoted_char" not in t:
        t = t.rstrip("\n") + """

/*
 * pg_dumpplus: Find the first occurrence of 'sep' in 's' that is not inside a
 * double-quoted SQL identifier ("" is an escaped quote).  Returns a pointer
 * into s, or NULL.
 */
char *
find_unquoted_char(const char *s, char sep)
{
\tbool\t\tin_quotes = false;

\twhile (*s)
\t{
\t\tif (*s == '\"')
\t\t{
\t\t\tif (in_quotes && s[1] == '\"')
\t\t\t\ts++;
\t\t\telse
\t\t\t\tin_quotes = !in_quotes;
\t\t}
\t\telse if (*s == sep && !in_quotes)
\t\t\treturn (char *) s;
\t\ts++;
\t}
\treturn NULL;
}
"""
        wr(su, t); changed.append(su)
    sh = P("src","include","fe_utils","string_utils.h"); t = rd(sh)
    t = rep_once(t, "#endif\t\t\t\t\t\t\t/* STRING_UTILS_H */",
        "extern char *find_unquoted_char(const char *s, char sep);\t/* pg_dumpplus */\n\n#endif\t\t\t\t\t\t\t/* STRING_UTILS_H */",
        "suh")
    wr(sh, t); changed.append(sh)

    # ---------- 4) pg_dump.c ----------
    d = P("src","bin","pg_dump","pg_dump.c"); t = rd(d)
    PG13 = "pg_fatal(" not in t      # PG13'te pg_fatal yok -> fatal()
    if "pg_dumpplus" not in t:
        # 4a: statik listeler
        t = rep_once(t, "static SimpleOidList tabledata_exclude_oids = {NULL, NULL};",
            "static SimpleOidList tabledata_exclude_oids = {NULL, NULL};\n"
            "/* pg_dumpplus: --where desenleri ve cozumlenmis OID'leri */\n"
            "static SimpleStringList tabledata_where_patterns = {NULL, NULL};\n"
            "static SimpleOidList tabledata_where_oids = {NULL, NULL};",
            "dd-statics")
        # 4b: long_options (opsiyon kodu 26; 13/17/18'de bos)
        t = rep_once(t, '{"include-foreign-data", required_argument, NULL, 11},',
            '{"include-foreign-data", required_argument, NULL, 11},\n\t\t{"where", required_argument, NULL, 26},\t/* pg_dumpplus */',
            "dd-longopt")
        # 4c: case 26 — case 11 blogundan hemen sonra
        m11 = re.search(r"case 11:[^\0]*?break;\n", t)
        if not m11: raise Fail("anchor [dd-case11] yok")
        t = t[:m11.end()] + """
\t\t\tcase 26:\t\t\t\t/* pg_dumpplus: --where=PATTERN:FILTER */
\t\t\t\tsimple_string_list_append(&tabledata_where_patterns, optarg);
\t\t\t\tbreak;

""" + t[m11.end():]
        # 4d: version banner -> progname bazli. Dikkat: [pg_dumpplus] etiketi
        # YALNIZ progname==pg_dumpplus iken basilir; ayni dizindeki pg_dumpall,
        # pg_dump --version ciktilarinin "pg_dump (PostgreSQL) X.Y" regex'ine
        # uymasini bekler (ayni-version kontrolu) — aksi halde TAP 001/002 cakisir.
        v1 = 'puts("pg_dump (PostgreSQL) " PG_VERSION);'
        v2 = 'printf("pg_dump (PostgreSQL) " PG_VERSION "\\n");'
        vnew = ('if (strcmp(progname, "pg_dump") == 0)\n'
                '\t\t\t\tprintf("%s (PostgreSQL) %s\\n", progname, PG_VERSION);\n'
                '\t\t\telse\n'
                '\t\t\t\tprintf("%s (PostgreSQL) %s [pg_dumpplus]\\n", progname, PG_VERSION);')
        if v1 in t:   t = rep_once(t, v1, vnew, "dd-ver-puts")
        elif v2 in t: t = rep_once(t, v2, vnew, "dd-ver-printf")
        else: raise Fail("dd-version anchor yok")
        # 4e: help
        t = rep_once(t, 'printf(_("\\nConnection options:\\n"));',
            'printf(_("  --where=PATTERN:FILTER   dump only rows matching SQL FILTER for\\n"\n'
            '\t\t\t\t\t "                               tables matching PATTERN (pg_dumpplus)\\n"));\n'
            '\tprintf(_("\\nConnection options:\\n"));', "dd-help")
        # 4f: forward decl
        mfwd = re.search(r"static void expand_table_name_patterns\(Archive \*fout,\n[^\0]*?\);\n", t)
        if not mfwd: raise Fail("anchor [dd-fwd] yok")
        fwd = mfwd.group(0)
        fwd_new = fwd[:-len(");\n")] + ", bool with_extra_data);\n"
        t = t[:mfwd.start()] + fwd_new + t[mfwd.end():]
        # 4g: tanim imzasi
        mdef = re.search(r"static void\nexpand_table_name_patterns\(Archive \*fout,\n"
                         r"[ \t]+SimpleStringList \*patterns, SimpleOidList \*oids,\n"
                         r"[ \t]+bool strict_names(, bool with_child_tables)?\)\n", t)
        if not mdef: raise Fail("anchor [dd-def] yok")
        has_children = mdef.group(1) is not None
        t = t[:mdef.start()] + mdef.group(0).replace(")\n", ", bool with_extra_data)\n") + t[mdef.end():]
        # 4g2: govde duzenlemeleri (yalniz bu fonksiyon diliminde)
        dstart = mdef.end()
        dend = t.find("\n\tdestroyPQExpBuffer(query);\n}\n", dstart)
        if dend < 0: raise Fail("dd-govde sonu yok")
        body = t[dstart:dend]
        body = rep_once(body,
            "\tPQExpBuffer query;\n\tPGresult   *res;\n\tSimpleStringListCell *cell;\n\tint\t\t\ti;\n",
            "\tPQExpBuffer query;\n\tPGresult   *res;\n\tSimpleStringListCell *cell;\n\tchar\t   *extra_data;\t/* pg_dumpplus */\n\tint\t\t\ti;\n",
            "dd-locals")
        colon_err = ("\t\t\t\tfatal(\"missing \\\":FILTER\\\" part in --where pattern \\\"%s\\\"\",\n"
                     "\t\t\t\t\t\tcell->val);\n") if PG13 else \
                    ("\t\t\t\tpg_fatal(\"missing \\\":FILTER\\\" part in --where pattern \\\"%s\\\"\",\n"
                     "\t\t\t\t\t\t cell->val);\n")
        body = rep_once(body, "\tfor (cell = patterns->head; cell; cell = cell->next)\n\t{\n",
            "\tfor (cell = patterns->head; cell; cell = cell->next)\n\t{\n"
            "\t\t/*\n\t\t * pg_dumpplus: with_extra_data ise desen 'TABLO:FILTRE' bicimindedir;\n"
            "\t\t * tirlimak icinde olmayan ilk ':' ayiracindan bol, sag tarafi extra_data olur.\n"
            "\t\t */\n"
            "\t\textra_data = NULL;\n"
            "\t\tif (with_extra_data)\n"
            "\t\t{\n"
            "\t\t\tchar\t   *colon = find_unquoted_char(cell->val, ':');\n\n"
            "\t\t\tif (colon == NULL)\n"
            + colon_err +
            "\t\t\t*colon = '\\0';\n"
            "\t\t\textra_data = pg_strdup(colon + 1);\n"
            "\t\t}\n\n", "dd-split")
        body = rep_once(body,
            "simple_oid_list_append(oids, atooid(PQgetvalue(res, i, 0)));",
            "simple_oid_list_append_data(oids,\n\t\t\t\t\t\t\t\t\t\t\t\t\t  atooid(PQgetvalue(res, i, 0)),\n\t\t\t\t\t\t\t\t\t\t\t\t\t  extra_data);",
            "dd-append")
        t = t[:dstart] + body + t[dend:]
        # 4h: mevcut cagri noktalarina 'false'
        if has_children:
            t, ncalls = re.subn(r"expand_table_name_patterns\(fout,\s+(&\w+),\s+(&\w+),\s+(strict_names|false),\s+(true|false)\);",
                                r"expand_table_name_patterns(fout, \1,\n\t\t\t\t\t\t\t   \2,\n\t\t\t\t\t\t\t   \3, \4, false);", t)
        else:
            t, ncalls = re.subn(r"expand_table_name_patterns\(fout,\s+(&\w+),\s+(&\w+),\s+(strict_names|false)\);",
                                r"expand_table_name_patterns(fout, \1,\n\t\t\t\t\t\t\t   \2,\n\t\t\t\t\t\t\t   \3, false);", t)
        if ncalls < 2: raise Fail(f"dd-cagri noktalan yetersiz ({ncalls})")
        # 4i: --where genisletme cagrisi — son genisletme sonrasina
        where_args = "true, false, true" if has_children else "true, true"
        mask_args = "true, false, false" if has_children else "true, false"
        last = max(x.end() for x in re.finditer(r"expand_table_name_patterns\(fout[^\0]*?\);\n", t))
        no_match_err = 'fatal("no matching tables were found for --where pattern");' if PG13 \
                       else 'pg_fatal("no matching tables were found for --where pattern");'
        t = t[:last] + ("\n\t/* pg_dumpplus: --where=PATTERN:FILTER desenlerini OID'lere coz */\n"
                        "\tif (tabledata_where_patterns.head != NULL)\n"
                        "\t{\n"
                        "\t\texpand_table_name_patterns(fout, &tabledata_where_patterns,\n"
                        "\t\t\t\t\t\t\t\t\t   &tabledata_where_oids,\n"
                        f"\t\t\t\t\t\t\t\t\t   {where_args});\n"
                        "\t\tif (tabledata_where_oids.head == NULL)\n"
                        f"\t\t\t{no_match_err}\n"
                        "\t}\n\n") + t[last:]
        # 4j: makeTableDataInfo
        mmt = re.search(r"static void\nmakeTableDataInfo\(DumpOptions \*dopt, TableInfo \*tbinfo\)\n\{\n\tTableDataInfo \*tdinfo;\n", t)
        if not mmt: raise Fail("anchor [dd-mtdi-head] yok")
        t = t[:mmt.end()] + "\tchar\t   *filter_clause;\t\t/* pg_dumpplus */\n" + t[mmt.end():]
        t = rep_once(t, "\ttdinfo->filtercond = NULL;\t/* might get set later */",
            "\ttdinfo->filtercond = NULL;\t/* might get set later */\n\n"
            "\t/*\n\t * pg_dumpplus: --where=PATTERN:FILTER bu tabloya eslesiyorsa filtercond'u kur.\n"
            "\t * Ornegin filter_clause \"created_at >= '2026-09-15'\" ise dump sorgusuna\n"
            "\t * \"WHERE (created_at >= '2026-09-15')\" eklenir (COPY ya da INSERT yolu).\n"
            "\t */\n"
            "\tfilter_clause = NULL;\n"
            "\tif (simple_oid_list_find_data(&tabledata_where_oids,\n"
            "\t\t\t\t\t\t\t\t\t\t\t\t\ttbinfo->dobj.catId.oid,\n"
            "\t\t\t\t\t\t\t\t\t\t\t\t\t(void **) &filter_clause) && filter_clause)\n"
            "\t{\n"
            "\t\tif (tdinfo->dobj.objType != DO_TABLE_DATA)\n"
            "\t\t\tpg_log_warning(\"pg_dumpplus: --where filter for \\\"%s\\\" ignored: object is not plain table data\",\n"
            "\t\t\t\t\t  tbinfo->dobj.name);\n"
            "\t\telse\n"
            "\t\t\ttdinfo->filtercond = psprintf(\"WHERE (%s)\", filter_clause);\n"
            "\t}", "dd-mtdi-filter")
        wr(d, t); changed.append(d)

    # ---------- 5) pg_dump.c: --mask (KVKK/GDPR kolon maskeleme) ----------
    if "{\"mask\", required_argument" not in t:
        # 5a: statikler + kayit tipi
        t = rep_once(t, "static SimpleOidList tabledata_where_oids = {NULL, NULL};",
            "static SimpleOidList tabledata_where_oids = {NULL, NULL};\n"
            "/* pg_dumpplus: --mask desenleri ve cozumlenmis kayitlari */\n"
            "static SimpleStringList tabledata_mask_patterns = {NULL, NULL};\n"
            "typedef struct DumpMaskEntry\n"
            "{\n"
            "\tstruct DumpMaskEntry *next;\n"
            "\tOid\t\t\t\t\trelid;\n"
            "\tchar\t   *colname;\n"
            "\tchar\t   *expr;\n"
            "\tbool\t\t\ttext_ret;\t\t/* preset text uretiyor */\n"
            "\tbool\t\t\tskip;\t\t\t/* validation'da true olur */\n"
            "} DumpMaskEntry;\n"
            "static DumpMaskEntry *dump_mask_entries = NULL;\n"
            "/* pg_dumpplus: forward decls (tanimlar fmtCopyColumnList oncesi) */\n"
            "static char *mask_expr_for(Oid relid, const char *colname);\n"
            "static bool table_has_masks(TableInfo *tbinfo);\n"
            "static const char *fmtMaskedColumnList(const TableInfo *ti,\n"
            "\t\t\t\t\t\t\t\t\t\t\tPQExpBuffer buffer);",
            "dm-statics")
        # 5b: long_options 27 (26=where'den sonra)
        t = rep_once(t, '{"where", required_argument, NULL, 26},\t/* pg_dumpplus */',
            '{"where", required_argument, NULL, 26},\t/* pg_dumpplus */\n'
            '\t\t{"mask", required_argument, NULL, 27},\t\t/* pg_dumpplus */',
            "dm-longopt")
        # 5c: case 27 (case 26 blogundan hemen sonra)
        t = rep_once(t, "\t\t\tcase 26:\t\t\t\t/* pg_dumpplus: --where=PATTERN:FILTER */\n"
                        "\t\t\t\tsimple_string_list_append(&tabledata_where_patterns, optarg);\n"
                        "\t\t\t\tbreak;\n",
            "\t\t\tcase 26:\t\t\t\t/* pg_dumpplus: --where=PATTERN:FILTER */\n"
            "\t\t\t\tsimple_string_list_append(&tabledata_where_patterns, optarg);\n"
            "\t\t\t\tbreak;\n"
            "\t\t\tcase 27:\t\t\t\t/* pg_dumpplus: --mask=PATTERN:COLUMN:EXPR */\n"
            "\t\t\t\tsimple_string_list_append(&tabledata_mask_patterns, optarg);\n"
            "\t\t\t\tbreak;\n",
            "dm-case")
        # 5d: help — --where satirindan once
        where_help = 'printf(_("  --where=PATTERN:FILTER   dump only rows matching SQL FILTER for\\n"'
        t = rep_once(t, where_help,
            'printf(_("  --mask=PATTERN:COLUMN:EXPR   replace COLUMN value with EXPR in dumped\\n"'
            '\t\t\t\t\t "                               data; EXPR: SQL or preset tc|phone|all\\n"));\n'
            + where_help, "dm-help")
        # 5e: cozum blogu — --where cozum bloğunun ardina
        mw = re.search(r"if \(tabledata_where_oids\.head == NULL\)\n[ \t]*\S[^\0]*?\n[ \t]*\}\n", t)
        if not mw: raise Fail("anchor [dm-after-where] yok")
        fm_err = "fatal" if PG13 else "pg_fatal"
        block = (MASK_RESOLVE_C.replace("@@FM@@", fm_err)
                            .replace("@@ARGS@@", mask_args))
        t = t[:mw.end()] + block + t[mw.end():]
        wr(d, t); changed.append(d)

    # ---------- 6) pg_dump.c: maskeleme yardimcilari ve sorgu yollari ----------
    if "static const char *\nfmtMaskedColumnList" not in t:
        # 6a: yardimcilar fmtCopyColumnList tanimindan once
        mfc = re.search(r"static const char \*\nfmtCopyColumnList\(const TableInfo \*ti, PQExpBuffer buffer\)\n\{\n", t)
        if not mfc: raise Fail("anchor [dm-fmt] yok")
        pos = mfc.start()
        t = t[:pos] + MASK_HELPERS_C + MASK_FMT_C + t[pos:]
        # 6b: COPY (SELECT) provizyonu -> maskeli liste; restore header'a dokunulmaz
        t = rep_once(t,
            "column_list = fmtCopyColumnList(tbinfo, clistBuf);",
            "column_list = table_has_masks(tbinfo)\n\t\t\t\t\t? fmtMaskedColumnList(tbinfo, clistBuf)\n\t\t\t\t\t: fmtCopyColumnList(tbinfo, clistBuf);",
            "dm-colproj")
        # 6c: COPY (SELECT ...) TO dalini mask icin de tetikle
        t = rep_once(t,
            "if (tdinfo->filtercond || tbinfo->relkind == RELKIND_FOREIGN_TABLE)",
            "if (tdinfo->filtercond || table_has_masks(tbinfo) ||\n\t\ttbinfo->relkind == RELKIND_FOREIGN_TABLE)",
            "dm-copybranch")
        # 6d: --inserts cursor SELECT'inde maskeli kolon -> ifade
        t = rep_once(t,
            "\t\tif (tbinfo->attgenerated[i])\n\t\t\tappendPQExpBufferStr(q, \"NULL\");\n\t\telse\n\t\t\tappendPQExpBufferStr(q, fmtId(tbinfo->attnames[i]));",
            "\t\tif (tbinfo->attgenerated[i])\n\t\t\tappendPQExpBufferStr(q, \"NULL\");\n"
            "\t\telse\n\t\t{\n\t\t\t/* pg_dumpplus: masked column -> emit masking expression */\n"
            "\t\t\tchar\t   *mexpr = mask_expr_for(tbinfo->dobj.catId.oid,\n\t\t\t\t\t\t\t\t\t\ttbinfo->attnames[i]);\n\n"
            "\t\t\tif (mexpr)\n"
            "\t\t\t\tappendPQExpBuffer(q, \"%s AS %s\", mexpr, fmtId(tbinfo->attnames[i]));\n"
            "\t\t\telse\n"
            "\t\t\t\tappendPQExpBufferStr(q, fmtId(tbinfo->attnames[i]));\n\t\t}",
            "dm-inserts")
        # 6e: makeTableDataInfo'da dogrulama — filtercond blogunun sonrasina
        anchor6e = "\t\t\ttdinfo->filtercond = psprintf(\"WHERE (%s)\", filter_clause);\n\t}"
        t = rep_once(t, anchor6e, anchor6e + "\n" + MASK_VALIDATE_C, "dm-validate")
        wr(d, t); changed.append(d)

    # ---------- 7) Makefile: pg_dumpplus hedefi ----------
    mk = P("src","bin","pg_dump","Makefile"); t = rd(mk)
    if "pg_dumpplus" not in t:
        m_link = re.search(r"^pg_dump: [^\n]*\n\t\$\(CC\)[^\n]*-o \$@\S*\n", t, re.M)
        if not m_link: raise Fail("mk-link anchor yok")
        block = m_link.group(0)
        t = t[:m_link.end()] + "# pg_dumpplus: ayni nesnelerden ikinci bagimsiz binary\n" + \
            block.replace("pg_dump:", "pg_dumpplus:", 1) + t[m_link.end():]
        m_inst = re.search(r"^install: all installdirs\n(\t\$\(INSTALL_PROGRAM\) pg_dump[^\n]*\n)", t, re.M)
        if not m_inst: raise Fail("mk-install anchor yok")
        t = t[:m_inst.end(1)] + "\t$(INSTALL_PROGRAM) pg_dumpplus$(X) '$(DESTDIR)$(bindir)'/pg_dumpplus$(X)\n" + t[m_inst.end(1):]
        t = re.sub(r"^all: pg_dump( pg_dumpplus)? pg_restore pg_dumpall$",
                   "all: pg_dump pg_dumpplus pg_restore pg_dumpall", t, flags=re.M)
        m_clean = re.search(r"^clean distclean[^\n]*:$", t, re.M)
        if m_clean:
            t = t[:m_clean.end()] + re.sub(r"rm -f pg_dump\$\(X\)", "rm -f pg_dump$(X) pg_dumpplus$(X)", t[m_clean.end():], count=1)
        wr(mk, t); changed.append(mk)

    state = {
        "patcher": patcher_hash,
        "files": {name: digest(pending[P(name)]) for name in PATCH_FILES},
    }
    written = []
    try:
        for path, content in pending.items():
            atomic_write(path, content)
            written.append(path)
        atomic_write(manifest, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode())
    except OSError:
        for path in reversed(written):
            atomic_write(path, originals[path])
        raise
    print("UYGULANDI:", ", ".join(os.path.relpath(p, root) for p in pending))

if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except (Fail, OSError, ValueError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)
