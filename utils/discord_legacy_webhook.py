# Allows for interacting with discord through webhooks, should someone ever find a need for that when self hosting 
import requests


class DiscordWebhook:
    def __init__(self, url: str, username: str):
        self.url = url
        self.username = username

    def send(self, content: str, title: str):
        data = { # https://discordapp.com/developers/docs/resources/webhook#execute-webhook
            "username" : self.username
        }
        data["embeds"] = [ # https://discordapp.com/developers/docs/resources/channel#embed-object
            {
                "description" : content,
                "title" : title
            }
        ]
        result = requests.post(self.url, json = data)

        result.raise_for_status()
        
        return True
