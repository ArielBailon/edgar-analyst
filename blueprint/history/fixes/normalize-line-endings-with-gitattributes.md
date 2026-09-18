# Fix: Normalize line endings with .gitattributes

**Type:** Fix
**Status:** verified
**Branch:** `fix/normalize-line-endings-with-gitattributes`

## The problem

The repository has no `.gitattributes`, so line endings are decided per machine by
each developer's `core.autocrlf`. This clone has `core.autocrlf=true`, which checks
every text file out as CRLF while Git stores it as LF. The index is already 100 percent
LF (75 text files stored `i/lf` with `w/crlf`, zero stored CRLF), so the repository
content is consistent. Only the working copy diverges, and it diverges differently
depending on who cloned it.

That divergence breaks any contract that hashes on-disk file bytes. It was caught
during feature 5's completion: recomputing the overview fingerprint from the CRLF
working copy produced `a9f6d38e...`, while the committed marker is `fb1cc35a...`,
computed over the same content with LF. The plans had not drifted at all. Writing the
CRLF-derived value would have made `/status` report phantom plan drift for every LF
checkout, including CI and any non-Windows clone. The wrong value was reverted, so no
bad hash is committed, but the hazard is still live for the next contributor and for
build-plan items 9 through 12, which add more file-reading tooling.

## The fix

Add a `.gitattributes` at the repository root declaring `* text=auto eol=lf`, then
refresh the working copy so the checked-out bytes match what Git stores.

- `text=auto` keeps Git's existing normalize-to-LF-on-commit behavior, now stated in
  the repository instead of inferred from each machine's config.
- `eol=lf` is the half that actually fixes the defect: it pins the working copy to LF
  regardless of `core.autocrlf`, so on-disk bytes equal the canonical bytes everywhere.

This must not rewrite repository content. The index is already all LF, so no stored
blob may change. The only expected change is working-copy line endings on this machine
and the new file itself.

Explicitly out of scope: changing `core.autocrlf` (a machine-level setting, not a
repository one), reformatting any file, and touching the overview fingerprint, which is
already correct.

## Build steps

- [x] 1. Add `.gitattributes` with `* text=auto eol=lf`, then re-checkout the working
  copy from the index so the new attribute applies to already-tracked files.
  **Done when:** `git ls-files --eol` reports no `w/crlf` entry for any text file;
  `git status` shows only the new `.gitattributes` as a change, proving no tracked blob
  was renormalized; and `git diff --cached --stat` after staging lists `.gitattributes`
  alone.

## Verify

1. `git ls-files --eol | grep -c "w/crlf"` returns 0.
2. `git status --porcelain` lists only `.gitattributes` before staging.
3. Recompute the overview fingerprint from the on-disk bytes using the documented
   contract (exact `project-plan.md` bytes, one zero byte, then `build-plan.md` with
   `- [x]` normalized to `- [ ]`). It must now equal the committed marker
   `fb1cc35a0360d7340bba355f359195dcd128f642c2cdd57a965e3edaaa17e375`, which is the
   proof the defect is gone.
4. `python -m app.retrieval.retriever "What risk factors does Apple disclose about
   supply chain concentration?"` still returns 5 cited results, confirming the
   re-checkout did not disturb the app.


<!-- blueprint:completion {"schemaVersion":1,"specBytes":3290,"specSha256":"8d9e66be3e692d14f08348c4b56bf65736cd7bd6eda59536178d4e1718b6f982","branch":"refs/heads/fix/normalize-line-endings-with-gitattributes","head":"054f9943ae242b43d95017055973e2e4ac61c7ac","baseRef":"refs/heads/master","baseCommit":"054f9943ae242b43d95017055973e2e4ac61c7ac","sourceTree":"adfcfdf36a63a0f329e82056ffabb3e8808d7bd1","absentOptional":[]} -->
