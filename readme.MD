## Set up

### Invite the bot to the server

We first need to generate an Invite Link for the Bot.

*   Log into the Discord Developer portal. 

*   Select the correct bot, e.g., Lectern.

*   In "OAuth2" section, select "URL Generator"

*   In Scope, check "bot". In Bot permissions, check "Administrator".

*   Copy the URL generated at the bottom of the page.

Then we invite the Bot to the server by opening the generated invite link in a
web browser. Select the server we want to invite the bot to, and then click
"Authorize" to add the bot to the server.

## Sync after commands are changed 

Type the following command to update commands in Discord server.

    //sync *

If everything works, the response is something like the following. 

    Synced 7 commands to the current guild.
