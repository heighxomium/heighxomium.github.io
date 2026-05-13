import urllib.request
import os
import re
import sys

URLS_FILE = os.path.join("scripts", "assets", "url.filters.txt")
OUTPUT_DIR = os.path.join("scripts", "generated")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "filters.txt")

UNSUPPORTED_OPTIONS = {
    "badfilter", "denyallow", "replace", "removeparam",
    "urlskip", "permissions", "from", "queryprune", "uritransform",
}

REDIRECT_OPTIONS = {"redirect", "redirect-rule"}

def read_urls(filepath):
    if not os.path.isfile(filepath):
        print(f"Error: URL file not found at {filepath}", file=sys.stderr)
        sys.exit(1)
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls

def download_list(url):
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode("utf-8").splitlines()
    except Exception as e:
        print(f"Warning: failed to download {url}: {e}", file=sys.stderr)
        return []

def convert_to_abp(raw_filter):
    f = raw_filter.strip()
    if not f or f.startswith("!") or (f.startswith("[") and f.endswith("]")):
        return None

    m = re.fullmatch(r"^(.+?)(?:\$([\w=~,|-]+))?$", f)
    if not m:
        pattern = f
        options_str = ""
    else:
        pattern = m.group(1)
        options_str = m.group(2) if m.group(2) else ""

    if not options_str:
        return pattern

    tokens = options_str.split(",")
    new_tokens = []

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        opt_name = tok.split("=", 1)[0].lstrip("~")

        if opt_name in UNSUPPORTED_OPTIONS:
            print(f"Dropping filter (unsupported option '{tok}'): {f}")
            return None

        if opt_name in REDIRECT_OPTIONS:
            print(f"Converting redirect to block by dropping option '{tok}': {f}")
            continue

        if tok == "1p":
            new_tokens.append("~third-party")
        elif tok == "3p":
            new_tokens.append("third-party")
        elif tok == "all":
            continue
        else:
            new_tokens.append(tok)

    if not new_tokens:
        return pattern
    return f"{pattern}${','.join(new_tokens)}"

def main():
    urls = read_urls(URLS_FILE)
    if not urls:
        print("Error: No URLs found in URL file", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filters_set = set()

    for url in urls:
        for line in download_list(url):
            converted = convert_to_abp(line)
            if converted:
                filters_set.add(converted)

    sorted_filters = sorted(filters_set)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write(f"! Title: Mix Filters ({len(sorted_filters)} filters)\n")
        for flt in sorted_filters:
            f.write(flt + "\n")

    print(f"Written {len(sorted_filters)} filters to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
