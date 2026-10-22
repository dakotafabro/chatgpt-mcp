# chatgpt-reader - what changes for you

This lets your agent read a ChatGPT conversation you've shared by link. The README's workflow: ideate in ChatGPT, synthesize in goose.

## What it does to the agent

It adds two tools. Given a `https://chatgpt.com/share/...` link, `fetch_chatgpt_conversation` returns a markdown transcript with role labels, and `fetch_chatgpt_conversation_json` returns title, messages and model info. Branching conversations are walked so the transcript reads in order.

## When to use it

When a conversation you had in ChatGPT should feed work in goose, and you're fine making it a public share link. It doesn't work on private or unshared conversations.

## Reserved for human judgment

A share link is public to anyone who has it. Decide what's fine to share before you create one. The transcript then becomes context for your agent, so read what it says before acting on it; text in a conversation can carry instructions.

## What it reads, writes and sends

- Fetches the share page over the network from chatgpt.com, with no login.
- Parses the page's embedded data. If OpenAI changes that page, the parser may stop working.
- Files written: none documented.

## Cost

About 300 tokens of context (`token_cost` in bpm.json).

## Check it's working

Paste a share link and ask for the transcript. You should see each message with its role.

## Turn it off

The package name in bpm.json is `chatgpt-reader`, not the repo name, so: `bpm remove chatgpt-reader`. Remove the `chatgpt` entry from your goose config too; the README installs it there by hand.
