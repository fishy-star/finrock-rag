# data/processed/

Staging area for original notes written *from* the reference ebook —
not the ebook's text itself. Per the content policy in
`finrock-rag-full-build-spec.md` §0, the ebook is the confirmed primary
content source for this project but must never be ingested verbatim
(commercial copyright, not a style preference). The intended workflow:

1. Read a chapter/section of the ebook.
2. Extract the *concept*, and write a short note in your own words —
   save it here as a `.txt` file.
3. Paste that note's contents into the "Upload a document" form in the
   web UI (or `POST /documents/upload`), tagged `source_type: internal_note`.

Nothing in the codebase reads this folder automatically — it's a place
to draft and keep original notes before they go through the upload
endpoint by hand, not an automated pipeline stage. If that ever changes
(e.g. a script that watches this folder and ingests on save), update
this file.
