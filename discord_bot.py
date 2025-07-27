import discord

class MyBot(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'We have logged in as {self.user}')

    async def send_message(self, channel_id, message):
        try:
            await self.wait_until_ready()
            channel = self.get_channel(channel_id)
            if channel is not None:
                await channel.send(message)
            else:
                print(f"Channel with ID {channel_id} not found.")
        except Exception as e:
            print(f"An error occurred: {e}")