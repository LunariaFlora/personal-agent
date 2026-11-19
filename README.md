# Personal Agent

A local-first personal workspace that starts from a chat box. Send it thoughts, links, images and files; whatever is worth keeping gets organised into notes that you can find again the next time the same topic comes up.

Everything runs on your own machine. There is no account, no telemetry, and no server component outside your computer. The web UI is a single local page served by a Python process at `http://127.0.0.1:8765`.

## The four entry points

The app deliberately separates four modes so that casual notes, real discussions, saved material and raw file transfers do not contaminate each other:

| Entry | What it is for |
|---|---|
| **Quick capture** | Thoughts, questions and screenshots sent in quick succession. The agent uses the surrounding context to decide what is worth keeping. |
| **Chat** | Discuss problems, look up old notes, use connected tools. Say "save this" or "bookmark this" when something should persist. |
| **Bookmarks** | Material is stored, parsed and classified by default; the original source is always kept. |
| **File transfer** | Stores text and attachments so you can copy, preview or download them. **This entry never sends content to a model and never participates in memory or knowledge search.** |

Enter sends, Shift+Enter inserts a newline. You can drag files in, paste screenshots, or use the paperclip. By default the app waits **60 seconds** after your last message before processing the batch; the *Done* button processes immediately. You can keep adding messages while a batch is being processed, and the reply waits for the new content. The wait time is configurable in settings.

Any message can be **quoted** to continue or annotate a specific thought. Organised notes keep a link back to the source entry, the original message and its attachments.

## Notes, memory and daily digest

- Notes support full-text search, browsing by folder and type, editing, and Markdown export. Folders are expressed with `/` (for example `education/study/math`), can be expanded level by level on the left, and may contain both notes and sub-folders.
- Drag the divider between panels to resize; the toolbar buttons collapse or expand the sidebar and list. The layout is remembered in the local browser.
- Creating and editing a note uses the whole main area, with a preview of the body.
- **Original text and source** shows the conversation, author, timestamps, quotes, forwards and attachments at the time. When you add to the same topic later, the agent looks for the existing topic, updates the relevant section, and appends the new wording. Editing an organised note never overwrites the original wording. If you edit the same note by hand while the agent is working on it, your edit is kept and the agent retries the round.
- Switch libraries in **Settings → current library**. Each library keeps its own chats, notes, memory, attachments and digest; model connections are shared. Replay libraries do not generate a digest automatically.
- Long-term preferences and things you explicitly asked to remember go into **memory**, which you can edit or delete directly. Long conversations are summarised automatically as context grows; the original conversation is always kept in full, and you can inspect or re-run the summary from the top-right corner of the chat.
- The **daily digest** picks one to three useful points from the day, based on when the source messages happened, what you were working on, and what has already been sent. It offers context, references or an optional next step, and shows the actual titles of the notes it cites. When generated automatically it stays quiet if there is nothing new worth sending; generating it manually rebuilds that day's digest.
- Digest defaults: time zone `America/Los_Angeles`, 09:00, both configurable. **The computer and the background service must be running.** Closing the chat window leaves the service running; while the machine is off no digest is generated. After a missed slot, the next start produces that day's digest once.

## Parsing and tools

Supported inputs: ordinary web article bodies, available Bilibili / YouTube subtitles and some platform articles; images (OCR plus scene description); PDF, DOCX and plain text extraction; local audio and video transcription; and question-driven sampling of video frames. Parse results distinguish body text, description, subtitles, transcription and sampled frames. When a page needs a login, has no subtitles, or is otherwise restricted, the app keeps the original link and states which parts could not be read. Frame sampling is not a substitute for watching frame by frame. Current limits: 1 GB per uploaded file, 2 hours per audio/video transcription.

Default model routing: text uses the configured DeepSeek connection, images use Kimi, speech uses Groq, and platform parsing uses the configured TikHub connection. Analysis sends only the content currently being processed to the corresponding service — the file transfer entry is excluded. All of this is adjustable in settings. With the official DeepSeek endpoint, web search reuses the same connection; an independent Brave key is also supported, falling back to public search pages when unavailable. Search summaries are labelled as leads and can be followed by reading the original page.

### MCP tools

Under **Settings → MCP tools** you can paste a standard `mcpServers` JSON object to connect stdio or Streamable HTTP servers:

```json
{
  "mcpServers": {
    "my_tool": {
      "command": "absolute/path/to/tool",
      "args": []
    }
  }
}
```

After saving, use *Test connection* to see which tools are actually discovered. The agent then decides during the conversation when to use them. `mcp-config.example.json` in this repository shows the shape of a Personal Agent client entry; replace the placeholder paths with your own before use.

## Importing conversations from another agent

Personal Agent also exposes its own MCP server. Start the desktop app first, then add the repository's `mcp-config.json` to the MCP configuration of another agent. You can also start the stdio server directly with `Start-MCP.ps1`.

The tools accept either an exported original JSON file plus its attachments, or a `{conversation, messages}` object. The flow is: `list_libraries` to choose a library, `import_original_chat` to begin, `get_import_status` to wait for completion, `find_original_messages` to locate original messages, `organize_messages` to hand a consecutive batch to the agent, `get_processing_status` to check progress, `search_notes` / `read_note` to review notes, and `read_original_context` to read the surrounding conversation.

Always pass an explicit `library_id` per call — `daily` for the everyday library, `mantingfang` for the replay library. Importing only stores the original conversation; the model is called only after you select messages. Re-importing does not duplicate messages, and attachments added in a later export are merged in. Instruction-like text found inside imported history never triggers external MCP actions on its own.

Original-chat and note searches return short previews page by page and read full text on demand, so a whole library is never pushed into a conversation at once. Imported-but-unorganised chats stay in the original archive rather than crowding the normal inbox; note sources still open the original text and nearby turns.

An exported JSON must keep the original message IDs, authors, timestamps and XML; attachment files and `media-manifest.json` must keep the directory layout produced by the export. A plain chat object needs at least `id`, `conversation_id`, `content`, a timezone-aware `created_at` and author information; `is_self` marks the user's own wording.

## Where things are stored

The application directory holds only code, launchers and documentation. The actual data lives outside it, under `<drive>:\AppData\PersonalAgent` by default, set through the `PERSONAL_AGENT_DATA` environment variable:

- `personal-agent.sqlite3` — chats, notes, memory and digests.
- `attachments` — original attachments; `notes` and `reports` — readable Markdown.
- `config.json`, `mcp.json` — local configuration, may contain API keys.
- `runtime`, `cache`, `logs` — Python runtime, caches and logs.
- `libraries/mantingfang` — replay library; `archives` — exported original conversations.

To back up, stop the service first and copy the data directory (`runtime`, `cache` and `logs` can be skipped). Restore by keeping the same layout. Run `Stop.ps1` to stop the background service; reopen the launcher to start it again.

## Requirements

- Windows 10/11 with PowerShell.
- Python 3.11 or newer. `Install.ps1` creates a virtual environment under the data directory and installs `requirements.txt` (FastAPI, uvicorn, trafilatura, pypdf, python-docx, Pillow, the MCP SDK and related packages). If `uv` is on PATH it is used, otherwise `python -m venv` and pip.
- ffmpeg and ffprobe on PATH for audio and video parsing.
- Google Chrome is preferred for the app window; any browser works as a fallback.

## Getting started

```powershell
# first run on a new machine
powershell -ExecutionPolicy Bypass -File .\Install.ps1

# start (also available as start-personal-agent.vbs)
powershell -ExecutionPolicy Bypass -File .\Start.ps1

# open directly
# http://127.0.0.1:8765
```

Model connections are entered in the app's settings screen; no key is hard-coded in the source.

## Project layout

```
personal_agent/        FastAPI app, engine, store, connectors, MCP server
  app.py               HTTP routes and static hosting
  engine.py            conversation and note orchestration
  store.py             SQLite persistence
  connectors.py        parsing and model adapters
  mcp_server.py        MCP server exposing the import tools
  libraries.py         per-library isolation
web/                   single-page front end (app.js, index.html, styles.css)
Install.ps1            create the runtime and install dependencies
Start.ps1 / Stop.ps1   start and stop the background service
Start-MCP.ps1          run the stdio MCP server
```

## Limitations

This is a single-machine desktop build. It does not connect to WeChat, does not require any other system to be running, and does not sync across devices. Mobile support, cross-device sync and a richer knowledge graph are possible later extensions. Digests need the machine to be on at the scheduled time.

## License

MIT. See `LICENSE`.
