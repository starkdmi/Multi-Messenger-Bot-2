# -*- coding: utf-8 -*-
import json
import random
import urllib
import urllib2
import webapp2

# tg sending images
import multipart

# vk sending images
from poster.encode import multipart_encode
from poster.encode import MultipartParam
from poster.streaminghttp import register_openers

# paint on image
import PIL
from StringIO import StringIO
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import textwrap

# specific languages
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

# Change standard deadline timing
urlfetch.set_default_fetch_deadline(120)

# ============================================================

# VK secret data | https://vk.com/dev/callback_api
VKServerConfirmationToken = "f5d9d45e"
VKServerSecretToken = "aaQ13axAPQEcczQa"
VKGroupToken = "VK_GROUP_TOKEN"

# Facebook secret data | https://developers.facebook.com/docs/messenger-platform/getting-started
FBServerConfirmationToken = "f5d9d45e"
FBGroupToken = "FACEBOOK_PAGE_TOKEN"

# Telegram secret data | https://core.telegram.org/bots/api
TelegramToken = "TELEGRAM_BOT_TOKEN"

# Telegram temporary chat id for upload images to Facebook via link
TelegramStorageChatId = "TELEGRAM_ADMIN_ACCOUNT_ID"

# System data
helpText = "Help ..."
aboutText = "About info ..."
#helloText = "I am Multi Messenger Bot created by starkov79."
unsupportedType = "This type of message does not supported."

ColorList = [(255, 155, 89, 182), (255, 41, 128, 185), (255, 127, 140, 141)]

# ============================================================

# Main function
def MessagesProcessing(data, dataType):
    if dataType == "text":
        if data.lower() in ["/help", "help", "помощь"]: # Help
            data = helpText
        elif data.lower() in ["/about", "about", "информация"]: # About
            data = aboutText
        else: # Echo
            # Choose a random background color
            BackgroundColor = random.choice(ColorList)

            # Setup text preferences
            lines = textwrap.wrap(data, width=18)
            img = Image.new('RGBA', (2048, 2048), BackgroundColor)
            draw = ImageDraw.Draw(img)
            fontsize = 200
            font = ImageFont.truetype('arial_unicode.ttf', fontsize)

            # Draw a text line by line
            StartHeight, TopMargin = (8 - len(lines)) * 128, 10
            for line in lines:
                TextWidth, TextHeight = draw.textsize(line, font=font)
                draw.text(((2048 - TextWidth) / 2, StartHeight), line, font=font) # line.encode('utf-8')
                StartHeight += TextHeight + TopMargin

            # Update an image
            output = StringIO()
            img.save(output, 'PNG')

            data = output.getvalue()
            dataType = "image"

    elif dataType == "image":
        output = StringIO()              
        data.save(output, "JPEG")
        data = output.getvalue()
    elif dataType == "undefined":
        data = unsupportedType
        dataType = "text"

    return data, dataType

# ============================================================

# Function for sending requests to VK
def VkRequest(method, arguments):
    # Add standart arguments
    arguments["access_token"] = VKGroupToken
    arguments["v"] = 5.65

    # Load request
    return urllib2.urlopen("https://api.vk.com/method/" + method, urllib.urlencode(arguments)).read()   

# Function for store images on Telegram servers side
def TelegramUploadImage(image):
    # Upload image to Telegram servers to access it via link
    resp = TelegramSendMessage(TelegramStorageChatId, image, "image")

    # Parse json response and get file id
    data = json.loads(resp)
    file_id = data["result"]["photo"][4]["file_id"] # 4 is a quallity of image, from 4 to 0, 4 is the best quallity

    # Recieve file path
    resp = urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/getFile?file_id=" + file_id).read()
        
    # Parse json response and get file path
    data = json.loads(resp)
    file_path = data["result"]["file_path"]

    # Generate file link
    return "https://api.telegram.org/file/bot" + TelegramToken + "/" + file_path

# Function for sending messages on VK
def VKSendMessage(userId, data, dataType):
    resp = 0
    if dataType == "text":
        resp = VkRequest("messages.send", {"user_id": userId, "message": data}) 
    elif dataType == "image":
        # Get url for uploading
        resp = json.loads(VkRequest("photos.getMessagesUploadServer", {"peer_id": userId}))     
        url = str(resp["response"]["upload_url"])

        # Upload image to VK server
        register_openers()
        data, headers = multipart_encode([MultipartParam(name="photo", value=data, filename="photo.png")])
        #datagen, headers = multipart_encode({"photo": open('512.png')}) # from file 
        request = urllib2.Request(url, "".join(data), headers) 
        resp = urllib2.urlopen(request).read()

        # Parse json response    
        data = json.loads(resp)

        # Save image on server
        resp = VkRequest("photos.saveMessagesPhoto", {"photo": data["photo"], "server": data["server"], "hash": data["hash"]})

        # Parse json response
        data = json.loads(resp)

        # Create attachment data
        owner_id = str(data["response"][0]["owner_id"])
        user_id = str(data["response"][0]["id"])
        attachment = "photo" + owner_id + "_" + user_id

        # Send photo to user
        resp = VkRequest("messages.send", {"user_id": userId, "message": "", "attachment": attachment})

    # If message was not sent
    if not resp.isdigit():
        # Error
        pass

# Function for sending messages on Facebook
def FBSendMessage(userId, data, dataType):
    if dataType == "text":
        # Generate json from arguments
        arguments = {"recipient": {"id": userId}, "message": {"text": data}, "messaging_type": "RESPONSE"}

        # Create message sending request
        request = urllib2.Request("https://graph.facebook.com/v2.6/me/messages?access_token=" + FBGroupToken, json.dumps(arguments), {"Content-Type": "application/json"}) # arguments.encode('utf-8').strip()

        # Send message
        urllib2.urlopen(request).read()

    elif dataType == "image" or dataType == "imagelink":
        imageLink = ""

        if dataType == "image": # Upload image to Telegram server
            imageLink = "https://vkmsgstat.appspot.com/image?url=" + str(TelegramUploadImage(data))
        else:
            imageLink = str(data)
        
        # Attach image via link
        arguments = {
            "messaging_type": "RESPONSE", 
            "recipient": {"id": userId}, # 1344879738923085
            "message": {
                "attachment": {
                    "type": "image", 
                    "payload": { 
                        "url": imageLink,
                        "is_reusable": True
                    }
                }
            }
        }

        data = json.dumps(arguments, ensure_ascii=False)

        # Send message
        request = urllib2.Request("https://graph.facebook.com/v2.6/me/messages?access_token=" + FBGroupToken, data, {"Content-Type": "application/json"}) 
        urllib2.urlopen(request).read()
    
# Function for sending messages on Telegram
def TelegramSendMessage(userId, data, dataType):
    if dataType == "text":
        return urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/sendMessage", urllib.urlencode({
                "chat_id": str(userId),
                "text": data,
                "disable_web_page_preview": "True"
            })).read()
    elif dataType == "image":
        return multipart.post_multipart("https://api.telegram.org/bot" + TelegramToken + "/sendPhoto", 
            [("chat_id", str(userId))],
            [("photo", "image.jpg", data)])

# ============================================================

# Callback class for answering to user messages from VK
class CallbackHandler(webapp2.RequestHandler):
    def post(self):
        # Get json data    
        data = json.loads(self.request.body)

        # Check if message was sent from VK server
        if data["secret"] != VKServerSecretToken:
            self.redirect('/')
    
        if data["type"] == "confirmation":
            # Return verification key to confirm server
            self.response.out.write(VKServerConfirmationToken)  
        elif data["type"] == "message_new":
            # Get user id
            user_id = data["object"]["user_id"]

            # Get message text
            text = data["object"]["body"]
            dataType = "text" 

            if text == "":
                dataType = "undefined" 

            # Get first attachment if it's photo and text is null
            if dataType == "undefined" and data["object"]["attachments"][0]["type"] == "photo":
                sizes = ["photo_2560", "photo_1280", "photo_807", "photo_604", "photo_130", "photo_75"]
                for size in sizes:
                    try:
                        photo_url = str(data["object"]["attachments"][0]["photo"][size])
                        text = Image.open(StringIO(urllib.urlopen(photo_url).read()))  
                        dataType = "image"
                        break
                    except:
                        pass                   

            # Process message text
            text, dataType = MessagesProcessing(text, dataType)
            
            # Answer to user
            VKSendMessage(str(user_id), text, dataType)

# Webhook class for answering to user messages from Facebook
class FBWebhookHandler(webapp2.RequestHandler):
    def get(self):
        # Get request arguments   
        mode = str(self.request.get('hub.mode'))
        verify_token = str(self.request.get('hub.verify_token'))
        challenge = str(self.request.get('hub.challenge'))
     
        if mode == "subscribe" and verify_token == FBServerConfirmationToken:
            # Return received key to confirm server
            self.response.out.write(challenge)
    
    def post(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(120)

        # Get json data    
        data = json.loads(self.request.body)

        # Parse data and get message text
        if data["object"] == "page":
            # Facebook can return more then one notify at time
            for entry in data["entry"]:
                # One notify can contain more then one message
                for messaging in entry["messaging"]: 
                    # Get sender id
                    userId = messaging["sender"]["id"]

                    # Get message text
                    text = ""
                    dataType = "text" 
                    try:                        
                        text = messaging["message"]["text"]                       
                    except:
                        # parse photo
                        pass
        
                    if text == "":
                        dataType = "undefined"

                    # Get first attachment if it's photo and text is null
                    try:
                        if dataType == "undefined" and messaging["message"]["attachments"][0]["type"] == "image": 
                            # Get link to attachment image   
                            text = str(messaging["message"]["attachments"][0]["payload"]["url"])
                            dataType = "imagelink"         
                    except:
                        pass

                    # Process message text
                    text, dataType = MessagesProcessing(text, dataType)

                    # Answer to user
                    try:
                        FBSendMessage(userId, text, dataType) 
                    except:
                        pass

# Webhook class for answering to user messages from Telegram
class WebhookHandler(webapp2.RequestHandler):
    def post(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(60)

        # Get json data 
        body = json.loads(self.request.body)

        # Getting message
        try:
            message = body["message"]
        except:
            message = body["edited_message"]

        dataType = "text" 
        data = message.get("text")       
        chatId = message["chat"]["id"]
 
        if not data:
            try: 
                photo = message["photo"]
                if photo:
                    photo_id = photo[2].get("file_id")
                    json_str= json.dumps(json.load(urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/getfile?file_id=" + photo_id)))
                    json_data = json.loads(json_str)
                    file_path = str(json_data.get("result")["file_path"])
                    photo_url = "https://api.telegram.org/file/bot" + TelegramToken + "/" + file_path
                    
                    data = Image.open(StringIO(urllib.urlopen(photo_url).read()))  
                    dataType = "image"
            except:
                dataType = "undefined" 

        # Process recieved data 
        data, dataType = MessagesProcessing(data, dataType)
    
        # Answer to chat
        resp = TelegramSendMessage(chatId, data, dataType)

# Additional classes for Telegram webhook handler
class MeHandler(webapp2.RequestHandler):
    def get(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/getMe"))))

class GetUpdatesHandler(webapp2.RequestHandler):
    def get(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/getUpdates"))))

class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(60)
        url = self.request.get("url")
        if url:
            self.response.write(json.dumps(json.load(urllib2.urlopen("https://api.telegram.org/bot" + TelegramToken + "/setWebhook", urllib.urlencode({"url": url})))))

# Additional class for upload images to Facebook
class FBImageHandler(webapp2.RequestHandler):
    def get(self):
        # Change deadline timing
        urlfetch.set_default_fetch_deadline(120)

        try:
            photo_url = str(self.request.get('url'))

            data = Image.open(StringIO(urllib.urlopen(photo_url).read()))
            output = StringIO()              
            data.save(output, "PNG")
            data = output.getvalue()

            self.response.headers['Content-Type'] = "image/png"
            self.response.body_file.write(data)
        except:
            pass

# Standard redirect class        
class AnotherHandler(webapp2.RequestHandler):
    def get(self):
        self.redirect('/')

# ============================================================

app = webapp2.WSGIApplication(routes=[  
    # Messages handlers
    ("/callback", CallbackHandler), # VK
    ("/facebookwebhook", FBWebhookHandler), # Facebook
    ("/webhook", WebhookHandler), # Telegram

    # Additional handlers
    ("/me", MeHandler), # Telegram
    ("/updates", GetUpdatesHandler), # Telegram
    ("/set_webhook", SetWebhookHandler), # Telegram  
    ("/image", FBImageHandler), # Facebook

    (r"/.*", AnotherHandler) ], debug=True)