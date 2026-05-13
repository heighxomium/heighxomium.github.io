import urllib.request
import os
import re
import sys

# Path to URL list
URLS_FILE = os.path.join("scripts", "assets", "url.filters.txt")
OUTPUT_DIR = os.path.join("scripts", "generated")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "filters.txt")

# Unsupported options that cannot be safely ignored → drop the whole filter
UNSUPPORTED_OPTIONS = {
    "badfilter", "denyallow", "replace", "removeparam",
    "urlskip", "permissions", "from", "queryprune", "uritransform",
}

# Options that will be converted to a simple block by omitting them
REDIRECT_OPTIONS = {"redirect", "redirect-rule"}

def read_urls(filepath):
    """Read list of URLs from file, ignoring empty lines and comments."""
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
    """Convert a uBO filter to ABP syntax. Returns the filter or None if it must be dropped."""
    f = raw_filter.strip()
    if not f or f.startswith("!") or (f.startswith("[") and f.endswith("]")):
        return None

    # Split pattern and options
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

        # Drop filter entirely if it contains an unusable option
        if opt_name in UNSUPPORTED_OPTIONS:
            print(f"Dropping filter (unsupported option '{tok}'): {f}")
            return None

        # Redirect options -> just omit them and turn filter into a block
        if opt_name in REDIRECT_OPTIONS:
            print(f"Converting redirect to block by dropping option '{tok}': {f}")
            continue

        # Workaround: uBO 1p/3p → ABP third-party
        if tok == "1p":
            new_tokens.append("~third-party")
        elif tok == "3p":
            new_tokens.append("third-party")
        elif tok == "all":
            # "all" is the default when no type option is given – safe to omit
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
        f.write("! Title: Mix Filters\n")
        for flt in sorted_filters:
            f.write(flt + "\n")

    print(f"Written {len(sorted_filters)} filters to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
