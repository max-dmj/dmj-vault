Update the debian changelog and version for a package.

Arguments: $ARGUMENTS
- First argument: package name. If not provided, guess by which files were updated since last commit.
- Second argument: version bump type — "major", "minor", or "patch" (default: "patch").

Steps:
1. Read `packaging/<package>/debian/changelog` and `packaging/<package>/debian/version.txt`.
2. Parse the current version from `version.txt` (format: MAJOR.MINOR.PATCH).
3. Bump the version according to the bump type:
   - "major": increment MAJOR, reset MINOR and PATCH to 0
   - "minor": increment MINOR, reset PATCH to 0
   - "patch": increment PATCH
4. Add a new entry at the **top** of `debian/changelog` in standard Debian format, summarizing the changes made in this session. Use today's date and the existing maintainer line from the previous entry. Do not ask for edit approval of `debian/changelog`.
5. Update `version.txt` with the new version. Do not ask for edit approval of `version.txt`.
