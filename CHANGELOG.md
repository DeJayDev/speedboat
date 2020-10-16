# Changelog

## V1.8

Me again! Discord API v8 Support, I give up on this changelog thing, just watch the commits or, optionally:

[Join the new hub for Speedboat.](https://discord.gg/am6SYkm)

## V1.7.0

Awesome, Python 3. The 1.7 branch of updates will all be counted as minors until the release of either LevelPlugin or XPPlugin.

### Features

- Moves away from the old Speedboat control guild
- Updates any python container to python3
- Updates to redis 5 (doing this slowly for compat reasons)
- Updates to postgres 9.6.17
- Updates to node 10
- Update all frontend dependencies and fix the incompatibilities
  - This is all part of an effort to reduce server load, where most of it comes from node.
- Updates all bot/web dependencies to something that supports python3 natively.

### Bug Fixes

- Properly uses Custom Status
- Moves to thecatapi (rip random.cat)


## V1.6.1

Hopefully this is how you do minor versions. This version fixes some things that I've observed to be broken and updates us to a newer version of peewee, for hopefully faster database queries.

### Features

- Updates to peewee3
- Moves everything to CommandSuccess or CommandFail
- Stores if a user was messaged when they were punished
- Adds invalid duration response to the parse_duration function
- Migrates to node:8.17-slim image
- Updates to postgres:9.6.16

### Bug Fixes

- Migrates to naturaltime instead of naturaldelta for commands that tell you how long ago something happen
- Changes some syntax of redis messages to fit how redis works now
- Fixes a upper/lower bound problem in the purge command
- Fixes get_dominant_colors_user in the stats command
- Fixes info to get the users avatar_url instead of building the url
- Fixes get_dominant_colors_user to use a real DiscoUser
- Fixes a bug in the unban command
- Fixes the guilds invite superuser command
- Fixes command in the archive command

## V1.6.0

**Merry Speedboat 1.6mas!**

This update attempts to catch Speedboat up to the rest of the rowboat clones by adding some fixes and community requested features.

### Features

- Removes the force option from setup
- Moves project to Parcel 📦 (Hopefully this reduces some server side load)
- Update rowboat and workers to Python 2.7.17
- Also updates all requirements to their newest versions (@dependabot was being annoying)
- Disable leave on guild unwhitelist (Speedboat left every guild it was apart of, not good)
- Adds requested !dog command (Thanks Tiemen.)
- Alias tempmute to timeout
- Defaults to the message author if no user is defined for info and log
- Brings the max reminders down to 15
- Switches back to b1nzy's disco repo
- Adds success message for purge
- Limits users returned by !search to 10.
- *Messages users when they are punished*

### Bug Fixes

- Properly load guilds in the core plugin
- Rewrote the frontend Dockerfile to fix some npm install issues
- Attempt to fix embed colors for guilds with transparent icons
- Update how the main guild channel is grabbed
- Fixes some upper bounds stuff with commands such as clean and archive
- Fixed a typo in the !clean command ("invaliud")
- Uses naturaltime instead of naturaldelta for that sweet sweet formatting.

## V1.5.0

**The skip forward update**

### Features 

- Adds a force option to setup
- Uses Discos `register_plugin_base_class`
- Uses Sentry's Unified SDK instead of Raven
- Begins removal of holster, because b1nzy said so

### Bugfixes
- **Fixed !cat** !!!
- Uses the new Discord CDN for emoji loading
- Removes usage of the deprecated trace packet
- Changes all public references of "Rowboat" back to "Speedboat"
- Changes how yaml files are loaded (be safe kids)

## V1.4.0

No.

## V1.3.0

### Features

- Added `archive extend` command which extends the duration of a current or expired archive
- Added some information to the guild overview/information page on the dashboard (thanks @swvn9)
- Added a spam bucket for max upper case letters (`max_upper_case`)
- Added `group_confirm_reactions` option to admin configuration, when toggled to true it will respond to !join and !leave group commands with only a reaction
- Added the ability to "snooze" reminders via reactions
- Added statistics around message latency
- Added a channel mention within the `SPAM_DEBUG` modlog event

### Bugfixes

- Fixed the response text of the `seen` command (thanks @OGNova)
- Fixed the infractions tab not showing up in the sidebar when viewing the config (thanks @OGNova)
- Fixed carriage returns not being counted as new lines in spam (thanks @liampwll)
- Fixed a bug with `mute` that would not allow a mute with no duration or reason to be applied
- Fixed case where long message deletions would not be properly logged (they are now truncated properly by the modlog)

## V1.2.0

### Features

- Twitch plugin added, can be used to track and notify a server of streams going online. (Currently early beta)

## V1.1.1

- Removed some utilities commands that didn't fit rowboats goal
- Etc SQL changes

## V1.1.0

### Features

- **MAJOR** Added support for audit-log reasons withing various admin actions. This will log the reason you provide for kicks/bans/mutes/etc within the Discord audit-log.
- **MAJOR** !mute behavior has changed. If a valid duration string is the first part of the reason, a !mute command is transformed into a tempmute. This should help resolve a common mistake people make.
- !join and !leave will no longer respond if no group roles are specified within the admin config
- Added a SQL command for global admins to graph word usage in a server.

### Bugfixes

- Fixed reloading of SQLPlugin in development
- Fixed some user images causing `get_dominant_colors` to return an incorrect value causing a command exception
- Fixed error case in modlog when handling VoiceStateUpdate
- Fixed a case where a user could not save the webconfig because the web access object had their ID stored as a string
- Fixed censor throwing errors when a message which was censored was already deleted

## V1.0.5

Similar changes to v1.0.4

## V1.0.4

### Bugfixes

- Fixed invalid function call causing errors w/ CHANGE\_USERNAME event

## V1.0.3

### Features

- Added two new modlog events, `MEMBER_TEMPMUTE_EXPIRE` and `MEMBER_TEMPBAN_EXPIRE` which are triggered when their respective infractions expire

### Bugfixes

- Fixed cases where certain modlog channels could become stuck due to transient Discord issues
- Fixed cases where content in certain censor filters would be ignored due to its casing, censor now ignores all casing in filters within its config

### Etc

- Don't leave the ROWBOAT\_GUILD\_ID, its special (and not doing this makes it impossible to bootstrap the bot otherwise)
- Improved the performance of !stats

## V1.0.2

### Bugfixes

- Fixed the user in a ban/forceban's modlog message being `<UNKNOWN>`. The modlog entry will now contain their ID if Rowboat cannot resolve further user information
- Fixed the duration of unlocking a role being 6 minutes instead of 5 minutes like the response message said
- Fixed some misc errors thrown when passing webhook messages to censor/spam plugins
- Fixed case where Rowboat guild access was not being properly synced due to invalid data being passed in the web configuration for some guilds
- Fixed the documentation URL being outdated
- Fixed some commands being incorrectly exposed publicly
- Fixed the ability to revoke or change ones own roles within the configuration

### Etc

- Removed `ignored_channels`, this concept is no longer (and hasn't been for a long time) used.
- Improved the performance (and formatting) around the !info command

## V1.0.1

### Bugfixes

- Fixed admin add/rmv role being able to operate on role that matched the command executors highest role.
- Fixed error triggered when removing debounces that where already partially-removed
- Fixed add/remove role throwing a command error when attempting to execute the modlog portion of their code.
- Fixed case where User.tempmute was called externally (e.g. by spam) for a guild without a mute role setup

## V1.0.0

### **BREAKING** Group Permissions Protection

This update includes a change to the way admin-groups (aka joinable roles) work. When a user attempts to join a group now, rowboat will check and confirm the role does not give any unwanted permissions (e.g. _anything_ elevated). This check can not be skipped or disabled in the configuration. Groups are explicitly meant to give cosmetic or channel-based permissions to users, and should _never_ include elevated permissions. In the case that a group role somehow is created or gets permissions, this prevents any users from using Rowboat as an elevation attack. Combined with guild role locking, this should prevent almost all possible permission escalation attacks.

### Guild Role Locking

This new feature allows Rowboat to lock-down a role, completely preventing/reverting updates to it. Roles can be unlocked by an administrator using the `!role unlock <role_id>` command, or by removing them from the config. The intention of this feature is to help locking down servers from permission escalation attacks. Role locking should be enabled for all roles that do not and should not change regularly, and for added protection you can disable the unlock command within your config.

```yaml
plugins:
  admin:
    locked_roles: [ROLE_ID_HERE]
```
