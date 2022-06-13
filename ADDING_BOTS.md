# Adding bots to BLAB

In order to integrate a chatbot with BLAB, it is necessary to create an intermediary program
that converts message representations between the formats used by BLAB and the bot.

See *models.py* for the definition of `Message`.

### Method 1 - Same Python environment

Ideal for development environments or trivial bots.

- Create a Python class that implements the `Bot` protocol defined in *bots.py*:
  - its constructor must have `conversation_info` (expained below) as its first positional argument;
  - its constructor may have other positional arguments or named arguments;
  - it must have a `receive_message` method that will be called whenever the conversation has a new message,
    which will be passed as the only argument (see the definition of `Message` in *models.py*).
  - since it will be instantiated for every message, in case some state has to be preserved between messages,
  use class members, databases or external files.

  The aforementioned `conversation_info` object has three members: `conversation_id` (id of the conversation),
  `bot_participant_id` (id of the participant correspondent to the bot) and `send_function` (a function that the bot
  should call to send messages to the user).

  Note that system messages (e.g. conversation created, participant joined, participant left) **and messages
  sent by the bot itself** will also cause `receive_message` to be called. Usually, the bot should
  ignore messages that were not sent by a human participant. If necessary, use the message's `sent_by_human()` method
  or check its type and compare its `sender_id` with the `conversation_info.bot_participant_id`.

- Install the bot in the same Python environment where BLAB Controller is installed.
- Edit the controller's settings (*dev.py* or *prod.py*) and include the new bot:

  ```python
  CHAT_INSTALLED_BOTS.update({
      'Name of your bot': (
          'your.bot.package',
          'your.bot.class',
          ['positional', 'arguments', 'for', 'the', 'bot', 'constructor'],
          {'named': 'arguments', 'for': 'the', 'bot': 'constructor'}
      )
  })
  ```
  The positional arguments will be passed **after** `conversation_info`.


### Method 2 - External program

- Implement a (possibly local) WebSocket client.

- Implement a simple (possibly local) HTTP(S) server that accepts POST requests on a specific URL.

- ...
