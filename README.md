# Win Or Try - Casino Bot Panel

This project has:
- A Discord bot in `bot.py` with `-roll`
- A web panel in React to start, stop, restart, and view logs
- A Node backend in `server.js` that controls the Python bot process

## Local run

```powershell
cd "c:\Users\marma\Discord bots\Casino Bot"
pip install -r requirements.txt
npm install
$env:DISCORD_TOKEN="YOUR_TOKEN"
npm start
```

Open `http://localhost:3000`.

## Railway deploy

1. Push this folder to your GitHub repo.
2. In Railway, create a project from that GitHub repo.
3. Railway will use the `Dockerfile` automatically.
4. Add Railway Variable (any one of these names works):
   - `DISCORD_TOKEN` = your bot token
   - `BOT_TOKEN` = your bot token
   - `TOKEN` = your bot token
5. Deploy.

Optional env:
- `PYTHON_BIN` if you want to override Python command.
- `PORT` is auto-set by Railway.

## Notes

- Keep bot token in Railway Variables, not in code.
- The panel starts/stops the bot process inside the same Railway service.
