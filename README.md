# Speedboat

Speedboat is a fork of Rowboat: A Discord bot focused on being a highly powerful and configurable moderation and utilitarian bot for Discord. Rowboat is built to feel and behave similarly to [AutoModerator](https://github.com/Deimos/AutoModerator) for reddit.

##### Main Discord

[![widget](https://inv.wtf/widget/dejay)](https://discord.gg/am6SYkm)

## Should I Run Speedboat Locally?

I mean, if you want to. The rowboat (and by extension Speedboat) has a lot of random moving pieces making spinning it up a bit more complicated. 

However, if you manage to pull it off, we have a place for people like you. 

DM me on Discord: DeJay#1337

## Development

Speedboat development is focused on the requirements of the servers seeking Speedboat for core moderation. Generally a good overview of general planned or in-development tasks is the [Trello Board](https://trello.com/b/FRCXmXKg), although its by no means a purely-true source.

### Can I Contribute?

It depends. Feel free to submit PRs, and we'll talk in your pull request. Feel free to have your server administrator reach out to me with your suggestions. 

(I am desperately seeking PRs focused around the frontend and web panel.)

### How Do I Contribute?

To get a local version of Speedboat running, you will need [docker-compose](https://docs.docker.com/compose/) setup locally. 

Once installed, you can simply run `docker-compose up` and in theory your dependencies should be setup. 

You may have to rerun the command after your first setup because of the way Postgres tables are created.
 
Postgres is going to give you some trouble, but the error message probably helps enough.

To give yourself global administrator, run `docker-compose exec web ./manage.py add-global-admin USER_ID_HERE`. 

Finally, you must make sure to copy the example configuration and properly replace the values within.

## Can I Use Speedboat?

Again, it depends. If you are interested in using Speedboat in your server, please message me and provide an invite alongside some general information about the server. At this time, Speedboat is only being added to larger (1-2k+ average CCU) servers that have more complex moderation requirements as we scale up to support more bots/become "public" (Google Forms application for the bot)

I am happy to add Speedboat to larger servers within the Minecraft community no questions asked.  
