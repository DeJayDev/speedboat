# Speedboat

Speedboat is a fork of Rowboat: A Discord bot focused on being a highly powerful and configurable moderation and utilitarian bot for Discord. Rowboat is built to feel and behave similarly to [AutoModerator](https://github.com/Deimos/AutoModerator) for reddit.

## Should I Run Speedboat Locally?

Probably not. The upstream project Rowboat has so many moving pieces that running a local version is complicated. If you manage to pull it off, we have a place for people like you. DM me on Discord: DeJay#1337

### Self-hosting Agreement

- You may not use the Rowboat logo or name within derivative bots.
- You may not host a public version of Rowboat.
- You may not charge for the usage of your instance of Rowboat.
- You may not provide support for Rowboat.

## Development

Speedboat development is focused on the requirements of the servers looking to move onto Speedboat as their core moderation bot. Generally a good overview of the planned or in-development tasks is the [Trello Board](https://trello.com/b/FRCXmXKg), although its by no means a purely-true source.

### Can I Contribute?

Maybe. Feel free to submit PRs, but unless they are explicitly bug fixes that have good documentation and clean code, I likely won't merge. Features will not be accepted through PR unless stated elsewhere. Do not submit feedback on this repository, have your server administrator contact me. PRs focused around the frontend and web panel are more likely to be accepted.

### How Do I Contribute?

To get a local version of rowboat running, you will need [docker-compose](https://docs.docker.com/compose/) setup locally. Once installed, you can simply run `docker-compose up` and in theory your dependencies should be setup. You may have to rerun the command after your first setup because of the way Postgres tables are created. To give yourself global administrator, run `docker-compose exec web ./manage.py add-global-admin USER_ID_HERE`. Finally, you must make sure to copy the example configuration and properly replace the values within.

## Can You Add Speedboat To My Server?

Maybe. If you are interested in using Speedboat in your server, please message me and provide an invite alongside some general information. Speedboat is only added to larger (1-2k+ average CCU) servers that have more complex moderation requirements. 

I am happy to add Speedboat to larger servers within the Minecraft community no questions asked.  
