## Summary verdict

GZWWWD.DLL is a **full FTP + HTTP download client with a cookie jar, an HTTP cache, URL parsing, an INI-style config store, and local-filesystem directory browsing** — i.e. the "WWW Download" networking core. This slice contains both protocol worker-thread run-loops, both response-body readers (chunked + content-length, with zlib inflate), the HTTP status-code dispatcher, the FTP command state-machines (RETR/STOR/LIST/login), and the complete cookie subsystem (parse / store / serialize / header-format). No HTML tag tables and no IRC code appear in this slice.

All strings/constants below are inline in the decompilation, cited `[CONFIRMED @ 0xADDR]`.

---

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100189e9,ftp,C2,sc3_ftp_parse_listing_line,"switch(param_3-0x12d) over FTP LIST styles; strstr ""<DIR>""/""<dir>""/""DIR""/""Disk size"" @0x100279d8/d0/b0/a4; skips ""."" ""..""=DAT_10027470/6c; builds entry via FUN_10005e8a+FUN_100060e0; case 0x10 parses 8.3 DOS names"
0x10013c8c,http,C2,sc3_http_read_body_chunked,"chunked transfer decode: isxdigit/strtoul chunk-size loop, strstr ""\r\n""@0x10027848/18, strcmp ""chunked""? via FUN_100155fb; zlib ctx local_98 (FUN_1000d92d/dd10/db9d); vtable recv @+0xec, 0x400 buf; content-length branch too"
0x1001301c,http,C2,sc3_http_worker_run,"HTTP worker thread loop: do/while + FUN_1000d391(1000000) 1s sleep; pops request queue @this+0xdc; retry count local_54[3]<3; parses Content-Length(id0x26)/Transfer-Encoding(id5 ""chunked""@0x10027840)/Connection(id2 ""close""@0x10027838); calls FUN_10013c8c body reader + FUN_10014ba8 dispatch"
0x1000b427,ini,C2,sc3_ini_read_section_pair,"reads config via vtable, skips ';' comments, stops at '[' section; splits key/value on DAT_100271a4; fmt ""%s %s""/""%s: %s"" @0x100273a4/0x10027398; emits pairs, dedups via FUN_10006e50"
0x10016673,ftp,C2,sc3_ftp_retr_file,"FTP download: ""PORT %d,%d,%d,%d,%d,%d""@0x100278c0, ""RETR %s""@0x100278e8, ""TYPE I""@0x100278dc (A/E variants for 0xc9/0xca); states 0x1f5-0x1fb, op 0x68; zlib compress local_94; progress callback msg 0x5738692e/2f"
0x10015f73,ftp,C2,sc3_ftp_stor_file,"FTP upload: ""STOR %s""@0x100278b4, ""PORT..."", ""TYPE I""; states 0x1f5-0x1fb, op 0x67; zlib decompress (FUN_1000dcd3) then FUN_10015dda send; progress msg 0x5738692c/2d"
0x100129ca,http,C2,sc3_http_build_request,"serialises HTTP request line+headers: ""http://""@0x1002782c, ""HTTP/1.1""@0x1002781c, "": ""@0x10027814, ""\r\n""@0x10027818; GET vs POST by FUN_10012848; iterates header array stride 0x18; proxy path via DAT_10027828/0x10027718"
0x100020f7,cookie,C2,sc3_cookie_parse_setcookie,"Set-Cookie/RFC2965 parser: _stricmp Comment/CommentURL/Domain/Path/Secure/Version/Discard/Expires/Max-Age/Port @0x1002719c..0x10027150; atoi+time() for Max-Age; splits attrs on ';'=DAT_100271a4; writes $domain/$path @0x10027144/0x1002713c"
0x1000409a,cache,C2,sc3_cache_eval_freshness,"HTTP Cache-Control eval: field ids 4/3/0x2c/0x2d (Date/Expires); _stricmp private/no-cache/must-revalidate/max-age/no-store @0x100271e8..0x1002710c; default TTL 0x3f480(259200s=3d); stores via cache vtable +0x5c/+0x60"
0x10004e1d,http,C2,sc3_http_dispatch_request,"request scheduler+cache lookup: age gates 500000/2000000 (param_3), builds ""Cookie""@0x10027224 header, FUN_100121cb enqueue; async callback msg 0x75758483; allocates request obj operator_new(0x1c)"
0x1000edce,fs,C2,sc3_fs_list_dir_filtered,"local dir enum via FindFirstFileA/FindNextFileA; dwFileAttributes&0x10 dir test; param_2 bitmask filter (1/2/4/8); compares names to DAT_10027454/58/50 ("".""/"".."" style); emits via FUN_1000c79c"
0x10016ce7,ftp,C2,sc3_ftp_list_dir,"FTP LIST: ""TYPE A""@0x10027900, ""PORT..."", ""LIST %s""@0x100278f4; states 0x1f5-0x1fb op 0x6f; recv loop grows buffer +0x100; parses result via FUN_10018902; msg 0x57386930"
0x1000e8c7,fs,C2,sc3_fs_enum_dir_sorted,"second local dir enumerator: FindFirstFileA/FindNextFileA, attr&0x10, DAT_10027454/58/50 name checks; builds sorted list (FUN_1000f720/f7ba/f6f4); dir-flag at param_1+0x2c/0x2d"
0x1000381f,cache,C2,sc3_cache_complete_entry,"[UNCERTAIN purpose] finalises a request: finds queued entry by id (this+0x58/0x5c lists), zlib compress/decompress body (FUN_1000dd10/dc8f) with size gates 0x1e8480/0x7a120 per level local_74; fires completion vtable +0xc/+8; missing: what the two lists represent"
0x10017f38,ftp,C2,sc3_ftp_login,"FTP connect+auth: ""USER %s""@0x10027984, ""PASS %s""@0x10027978, ""ACCT %s""@0x1002796c, ""SYST""@0x10027964; states 0x191-0x198, op 0x65; reply-code branch local_18; msg 0x57386938"
0x100150d3,ftp,C2,sc3_ftp_parse_listing_date,"parses date/time from FTP LIST: sscanf ""%s %s %s %s %s %s %s %s""@0x10027888 (3 formats via FUN_10014f0a); FUN_1001555b month, atoi day/year; year<0x32→+2000 else<100→+1900(0x76c); leap-year calc; day-of-year table DAT_10021bc8"
0x1001046e,url,C2,sc3_url_parse_scheme,"URL scheme classifier: sets scheme id this+4 (1..9); ""mailto:""@0x10027484, ftp/https/http/file/news/nntp/gopher via DAT_100274ec..0x1002748c; tolower's scheme; validates authority chars isalnum/+/-/."
0x10019ca4,ftp,C2,sc3_ftp_worker_run,"FTP worker thread loop: do/while + FUN_1000d391(1000000) sleep; pops queue this+0xc; op-type 5 builds FTP session obj local_b80 (FUN_10015820); calls FUN_10017f38 login + FUN_10016673 RETR; IP test FUN_1001b50e; default port FUN_100102da"
0x10014ba8,http,C2,sc3_http_dispatch_status,"HTTP response-code state machine: 200-299→state0 success; 300-399 redirect (Location field id0x1a, count param_2[3]<3); 401=0x191→state9 auth; else state8 error; per-method param_3 (1/6/7 GET, 2/3, 4/5)"
0x10001724,cookie,C2,sc3_cookie_store_match,"stores cookie/cache entry: domain match this+0xc with '.' rules, default port 0x50; expiry via time() vs entry[0x13] (==2 = session); evicts when count>this+0x10 via FUN_10002a51; entry stride 0x94"
0x100148bc,http,C2,sc3_http_read_body_length,"content-length body reader: reads local_14 bytes via vtable recv +0xf4/+0xec, 0x400 chunks; optional zlib inflate local_80 (FUN_1000d92d/dc8f); timeout via time() vs param_4+8; writes via FUN_10013a47/FUN_10006241"
0x10002f49,cookie,C2,sc3_cookie_jar_save,"serialises cookie jar to config: ""CookieData""@0x100270b4, ""CookieData%05u""@0x100271a8, ""Binary""@0x100271c0, ""Admin""@0x100271b8; iterates array stride 0x94, skips expired (time()<entry[0x13]); writes via FUN_1000b427/FUN_1000b1e1"
0x10001cd2,cookie,C2,sc3_cookie_format_header,"builds Cookie request header: iterates attr pairs stride 0x18, skips reserved comment/commenturl/discard/expires/max-age/secure/version/domain/path @0x10027130..0x100270e4; emits name=value ('='=0x3d) joined by ""; ""=DAT_10027138; caps at 1000 iters"
0x1000c012,ini,C2,sc3_ini_read_section_cb,"INI section reader w/ callback: reads lines via vtable +0x40, skips ';' comments, stops at '[', splits on '='=DAT_100271a4; builds pair list stride 0x28; invokes callback param_2(key,val,param_3) per entry"
0x1000814f,cache,C2,sc3_cache_insert_entry,"cache/cookie map insert w/ eviction: bumps counters this+0x54/0x58, evicts when >0x28(40) via FUN_1000865c; hashtable this+0x34; expiry local_48 = now+ttl (0x7fffffff if ttl<0); dup-check FUN_10006e50"
```

---

## 2. Notable findings (structural, high-value)

**Two protocol worker-thread run-loops** (the closest thing to "per-tick" entry points here):
- `FUN_1001301c` — HTTP transaction worker loop `[CONFIRMED @ 0x1001301c]`. Infinite `do/while` with `FUN_1000d391(1000000)` (1-second idle sleep), pops from request queue at `this+0xdc`, drives request→response→retry (max 3, `local_54[3]<3`), branches on `Content-Length`(hdr id 0x26) / `Transfer-Encoding: chunked` / `Connection: close`.
- `FUN_10019ca4` — FTP transfer worker loop `[CONFIRMED @ 0x10019ca4]`, same idle-sleep idiom, pops queue at `this+0xc`, constructs an FTP session object and calls login (`FUN_10017f38`) then RETR (`FUN_10016673`).

**Message-id / status dispatch tables:**
- `FUN_10014ba8` — HTTP **response-code → next-state** machine `[CONFIRMED @ 0x10014ba8]`: 200-299 success; 300-399 redirect (reads `Location`, field id `0x1a`); 401 (`0x191`) → auth state 9; retry cap 3.
- `FUN_100189e9` — FTP **LIST-format dispatcher** `[CONFIRMED @ 0x100189e9]`: `switch(param_3 - 0x12d)` selects among directory-listing grammars (Unix/DOS/VMS-style); message ids `0x12d`–`0x13x`.

**Serialisers (cookie jar — the full round-trip is in this slice):**
- `FUN_100020f7` — Set-Cookie **parser** (RFC 2965 attributes) `[CONFIRMED @ 0x100020f7]`.
- `FUN_10001cd2` — Cookie request-header **formatter** `[CONFIRMED @ 0x10001cd2]`.
- `FUN_10002f49` — cookie jar **save/persist** to a config store, keys `CookieData` / `CookieData%05u` `[CONFIRMED @ 0x10002f49]`.
- `FUN_10001724` / `FUN_1000814f` — cookie/cache **store + LRU eviction** (capacity `0x28`=40) `[CONFIRMED @ 0x1000814f]`.

**INI config store (read side, two variants):** `FUN_1000b427` and `FUN_1000c012` — comment char `;`, section char `[`, key/value split on `=` (`DAT_100271a4`) `[CONFIRMED @ 0x1000c012]`. `FUN_10002f49` writes through the same format, so the cookie jar is stored as an INI file.

**Named tunable constants (raw values, cite these):**
- FTP control-reply state codes: `0x1f5`–`0x1fb` (transfer states), `0x191`–`0x198` (login states) `[CONFIRMED @ 0x10016673, 0x10017f38]`.
- FTP data ops: RETR `0x68`, STOR `0x67`, LIST `0x6f`, login `0x65` `[CONFIRMED @ 0x10016673/0x10015f73/0x10016ce7/0x10017f38]`.
- Cache default freshness `0x3f480` = 259200 s = 3 days `[CONFIRMED @ 0x1000409a]`; cache age gates `500000` / `2000000` `[CONFIRMED @ 0x10004e1d, 0x1000381f]` (also as `0x7a120`/`0x1e8480`).
- Cookie/cache map capacity `0x28` = 40 entries; entry stride `0x94` bytes `[CONFIRMED @ 0x1000814f, 0x10001724, 0x10002f49]`.
- Body buffers: `0x400`, `0x4000`, `0x8000`, `0x20000` `[CONFIRMED @ 0x1001301c, 0x100148bc]`.
- Async progress/completion callback message ids: `0x5738692c`–`0x57386938`, `0x75758483` `[CONFIRMED @ 0x10015f73, 0x10017f38, 0x10004e1d]`.
- FTP LIST day-of-year cumulative-month table at `DAT_10021bc8` (indexed `*param_4*4`) `[CONFIRMED @ 0x100150d3, 0x10015196]`.

**zlib/gzip is pervasive:** `FUN_1000d92d` (stream init), `FUN_1000dd10`/`FUN_1000dc8f`/`FUN_1000dcd3` (inflate/deflate), `FUN_1000db9d`/`FUN_1000d9f6` (end) appear in every body reader and both FTP transfer paths — transfers are compressed on the wire. This is a strong candidate for a follow-up subsystem sweep (the `FUN_1000d9xx`/`FUN_1000dxxx` cluster is the zlib wrapper, mostly outside this size-ranked slice).

---

## 3. Not determined / partial

- **`FUN_1000381f`** (`sc3_cache_complete_entry`): mechanically clear (finds a queued entry by id across the two lists at `this+0x58`/`this+0x5c`, zlib-transforms the body with per-level size gates, fires a completion vtable call), but the **distinction between the `this+0x58` and `this+0x5c` lists is not determined** from this function alone. Missing evidence: the constructor/initialiser that populates those two lists, and the callers that read them. Classified `cache`/C2 on mechanics; purpose tag is `[UNCERTAIN]`.
- **Exact literal text of several `DAT_*` operands** was not read from `strings.csv` (e.g. `DAT_100279b8` used as a 4-char suffix in the FTP case 0xa/0xb, `DAT_10027470`/`DAT_1002746c` are the `.`/`..` compare targets by usage). Their **roles are confirmed by use-site**, but the raw bytes were not independently verified against `re/ghidra_export_gzwwwd/strings.csv`. If exact spellings are needed, grep those addresses in that file.
- **No per-frame Simulate/tick entry** exists in this module — the two `do/while(true)` loops (`FUN_1001301c`, `FUN_10019ca4`) are **network worker threads**, not sim ticks. This is consistent with GZWWWD being an I/O component rather than a sim subsystem.

All 25 functions in the slice were read and classified (C2). None left at C0.
