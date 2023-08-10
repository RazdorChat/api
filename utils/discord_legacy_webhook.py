# Allows for interacting with discord through webhooks, should someone ever find a need for that when self hosting
import requests


class DiscordWebhook:
    """A class for interacting with discord through webhooks.

    Args:
            url (str): The url of the webhook.
            username (str): The username of the webhook.
    """

    def __init__(self, url: str, username: str):
        self.url = url
        self.username = username

    def send(self, content: str, title: str) -> bool:
        """Sends a message to the webhook.

        Args:
                content (str): The content of the message.
                title (str): The title of the message.

        Returns:
                bool: True if the message was sent successfully, otherwise it should raise an exception.
        """
        data = {"username": self.username}  # https://discordapp.com/developers/docs/resources/webhook#execute-webhook
        data["embeds"] = [{"description": content, "title": title}]  # https://discordapp.com/developers/docs/resources/channel#embed-object
        result = requests.post(self.url, json=data)

        result.raise_for_status()

        return True
