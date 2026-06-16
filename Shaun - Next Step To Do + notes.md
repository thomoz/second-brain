

Start building "Ask Me Questions"

Saved to .agent/plans/ask-me-questions-handoff.md.

Next session flow:
1. /prime
2. Tell me to read ask-me-questions-handoff.md
3. Quick discussion to close the 6 open questions
4. /plan-feature to build the implementation plan





## Where we are up to:

/prime, then paste this:

Read .agent/plans/handoff-heartbeat-state-vps.md and fix the heartbeat state persistence issue on the VPS

Also, check iof we need so many heartbeats per day, espeiclaly since I'm asleep 8 hours a day.



## When aldi sim arrives:

A second SIM (Aldi prepaid) has been ordered. Once it arrives:
1. Register WhatsApp on the Aldi number
2. In GREEN-API: delete current instance → create new instance → scan QR with Aldi number
3. Update `.env`: new `WHATSAPP_INSTANCE_ID`, `WHATSAPP_API_TOKEN`, and Aldi number for instance
4. `WHATSAPP_MY_NUMBER` stays as `61410868612` (Shaun's personal number — used by security filter)
5. Update "Second Brain" phone contact to point to the new Aldi number: open Contacts on your iPhone → find "Second Brain" → edit the number to the new Aldi number.

.env is gitignored — it's never in GitHub (by design, it contains secrets), so you'll need to manually copy it to the VPS each time it changes:

:Run from your local machine
scp .claude/scripts/.env secondbrain@137.184.102.104:/home/secondbrain/second-brain/.claude/scripts/.env

Then restart the WhatsApp service on the VPS:
sudo systemctl restart second-brain-whatsapp.service

After this, messages arrive FROM the bot number TO Shaun's personal number → normal notifications.

Step 3 — your notes say "Aldi number for instance" but don't spell out which variable. That would be a new env var or just the instance credentials. WHATSAPP_MY_NUMBER (step 4) stays as your personal number 61410868612 — that's the security filter that ensures the bot only responds to you.

 OK - I have an old iphone. I'll see if that works.

Perfect — that's the ideal setup. Old iPhone on a charger running WhatsApp permanently = GREEN-API stays connected indefinitely.

Steps when the Aldi SIM arrives (these instructions from a later Claude session):

1. Put Aldi SIM in old iPhone → install WhatsApp → register Number B
2. In GREEN-API dashboard → create/configure your instance → scan QR code with the old iPhone's WhatsApp
3. Update .env on both local machine and VPS with the new WHATSAPP_INSTANCE_ID, WHATSAPP_API_TOKEN, and WHATSAPP_MY_NUMBER (your normal number, Number A)
4. Leave old iPhone on charger with WiFi + WhatsApp running permanently — that's what keeps GREEN-API connected long-term after you swap your normal SIM back into your main phone.
5. Put normal SIM back in your main phone

After that the bot should work end-to-end — messages arrive on your main phone with proper notifications, and your replies route back through GREEN-API correctly.








## Security for DigitalOcean VPS is covered in Agentic Coding Course:


## To change Heartbeat and Daily Reflection frequencies:

Change -Hours 4 to whatever interval you want, and "07:00" to your preferred start time:

Heartbeat (currently every 4 hours):
$t1 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 4) -Once -At "07:00"
$a1 = New-ScheduledTaskAction -Execute "uv" -Argument "run python heartbeat.py" -WorkingDirectory "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts"
Register-ScheduledTask -TaskName "SecondBrain-Heartbeat" -Trigger $t1 -Action $a1 -RunLevel Highest -Force

Change "03:00" to whatever time you want:

Reflection (currently 3am daily):
$t2 = New-ScheduledTaskTrigger -Daily -At "03:00"
$a2 = New-ScheduledTaskAction -Execute "uv" -Argument "run python memory_reflect.py" -WorkingDirectory "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts"
Register-ScheduledTask -TaskName "SecondBrain-Reflection" -Trigger $t2 -Action $a2 -RunLevel Highest -Force


## To change model used or to Codex subscription:

ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

That's it. The SB_AGENT_BACKEND stays as claude (the default). When ANTHROPIC_API_KEY is set, claude-code-sdk bills against the API key instead of the subscription — no code changes needed anywhere.

Cost controls already in place:
- CHAT_MAX_BUDGET_USD=0.50 — per-conversation spend cap for the WhatsApp bot
- CHAT_MAX_TURNS=20 — limits tool calls per response

Cheapest model option — if you want to reduce token costs, you can add:
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
Though sdk_compat.py doesn't currently pass a model to ClaudeAgentOptions for the chat bot — that's a one-line add to engine.py if you want it.

Alternative if API costs get high: SB_AGENT_BACKEND=pi is already built (Phase 2) — drives Pi which uses your OpenAI/Codex subscription instead. Pi isn't installed yet (npm install -g @earendil-works/pi-coding-agent would sort that), but the compat layer is ready.


