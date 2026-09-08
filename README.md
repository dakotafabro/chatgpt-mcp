# chatgpt-mcp

MCP server for reading shared ChatGPT conversations into Goose.

Paste a ChatGPT share link, get the full conversation transcript. Built for the workflow: **ideate in ChatGPT, synthesize in Goose**.

## Install

```bash
cd ~/development/chatgpt-mcp
uv pip install -e .
```

## Goose Config

Add to `~/.config/goose/config.yaml`:

```yaml
chatgpt:
  enabled: true
  type: stdio
  name: ChatGPT Reader
  description: Read shared ChatGPT conversations
  cmd: uv
  args:
    - run
    - --directory
    - /Users/dakotafabro/development/chatgpt-mcp
    - chatgpt-mcp
  envs: {}
  env_keys: []
  timeout: 30
  bundled: false
  available_tools: []
```

## Tools

### `fetch_chatgpt_conversation(url)`

Returns the conversation as a markdown transcript with role labels.

### `fetch_chatgpt_conversation_json(url)`

Returns structured JSON with title, messages array, model info.

## How It Works

1. Takes a ChatGPT share URL (`https://chatgpt.com/share/...`)
2. Fetches the HTML page (no auth needed for shared links)
3. Extracts conversation data from the React Router streaming payload or `__NEXT_DATA__`
4. Parses the message tree (handles branching conversations by walking the mapping)
5. Returns formatted transcript

## Limitations

- Only works with **publicly shared** conversations (via ChatGPT's Share button)
- Private/unshared conversations require auth and are not supported
- If OpenAI changes their share page HTML structure, the parser may need updating
