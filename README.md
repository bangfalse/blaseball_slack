# Blaseball Slack Bot

This is a bot which supports posting some information from the [Blaseball](https://blaseball.com) API to a Slack channel.

It is intended to be run regularly, e.g. as a `cron` job.

To use it, copy `config_example.json` to `config.json` and add a Slack access token, the channel you want to use, and the owner's Slack member ID.

Setting `extended_siesta` to `true` will stop new posts from being created, but will keep updating the most recent post if something changes.

It creates a single post and pins it to the channel every day, and then responds to it with every update the Ticker.

This may be extended to include the Feed and other features in the future, but no guarantees are made.
