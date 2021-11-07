# per installare queste librerie:
# 

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import subprocess
import exchange
import time
#import os
from .telegram_credentials import *

# IMPORTANTE: inserire il token fornito dal BotFather nella seguente stringa
TOKEN=get_token()

def func_call(filename):
  exec(open(filename).read(), globals(), globals())

def extract_number(text):
     return text.split()[1].strip()

def nulla():
     print("attivo")
     return False

#def telegram_idle():
def main():
     upd= Updater(TOKEN, use_context=True)
     disp=upd.dispatcher

     disp.add_handler(CommandHandler("bot1", nulla))

     upd.start_polling()

     #while True:
          #print("This prints once a minute.")
          #time.sleep(1) # Delay for 1 minute (60 seconds).
          #upd.idle()

if __name__=='__main__':
     main()