# -*-coding:Utf-8 -*
import mongoengine as db
from notif_server.notif import send_silent_notification
try:
    from instant_server.server.error_handler import prod_error_instant_mail
except:
    def prod_error_instant_mail(a, b, c, d):
        print a, b, c, d 
import datetime
import random
import time
import json

def connect(read_only=False):
    if read_only:
        READONLY_URI = 'mongodb://readit:thisisyourfrench@ds051160.mongolab.com:51160/heroku_app31307485'
        print "connecting to pictever database (read only)..."
        db.connect('picteverdb', host=READONLY_URI)
    else:
        PRODUCTION_URI = 'mongodb://testdb:test@ds051160.mongolab.com:51160/heroku_app31307485'
        print "connecting to pictever database ..."
        db.connect('picteverdb', host=PRODUCTION_URI)

class Message(db.Document):
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    delivery_time = db.DateTimeField(default=datetime.datetime.now, required=True)
    is_blocked = db.BooleanField(default=False)
    sender_id = db.ObjectIdField()
    receiver_id = db.ObjectIdField()
    receiver_phone = db.StringField()
    message = db.StringField(required=True)
    photo_id = db.StringField(default="", required=True)
    video_id = db.StringField(default="", required=True)
    sound_id = db.StringField(default="", required=True)
    notif_delivered = db.BooleanField(default=False, required=True)
    receive_label = db.StringField()
    receive_color = db.StringField()
    version = db.StringField()

    meta = {
        'indexes': ['-created_at', 'receiver_id'],
        'ordering': ['-delivery_time']
    }

    @staticmethod
    def resend(message_id):
        mes = Message.objects.with_id(message_id)
	user = User.objects.with_id(mes.receiver_id)
	counter = user.get_number_of_future_messages()
	delta = time.mktime(mes.delivery_time.utctimetuple()) - time.mktime(mes.created_at.utctimetuple())
	print "first delta", delta
	if delta < 10000000 or counter < 10:
	    delta = random.randint(3*10000000//4,5*10000000//4)
	rand = random.randint(3*delta//4, 5*delta//4)
	print "rand",rand
	t = time.mktime(mes.delivery_time.utctimetuple()) + rand
	r = ReceiveLabel.get_receive_label(t-time.mktime(mes.created_at.utctimetuple()))
	if user.country_code=='fr':
	    mes.receive_label = r.label_fr
	else:
	    mes.receive_label = r.label
	print r.label
	mes.receive_color = ReceiveLabel.get_rand_color()
	mes.delivery_time = datetime.datetime.fromtimestamp(t)
	mes.notif_delivered = False
	mes.save()
	return mes.id	

    @staticmethod
    def add_to_db(current_user, message, receiver_id,delivery_time_ts,photo_id,video_id,sound_id):
        if receiver_id[:2] == "id":
            print "id detected"
            receiver_id = receiver_id[2:]
	    country_code = User.objects.with_id(receiver_id).country_code
            receiver_phone = None
	    is_blocked = False
        elif receiver_id[:3] == "num":
            print "phone number then"
            receiver_phone = receiver_id[3:]
            receiver_id = current_user.id
	    if receiver_phone.startswith("0033"):
	    	country_code = 'fr'
	    else:
		country_code = 'us'
	    is_blocked = True	
        else:
            print "error cannot understand id"
            prod_error_instant_mail(
                error_num=100,
                object="add_to_db",
                details="{}".format("error cannot understand id : {}".format(receiver_id)),
                critical_level="ERROR")
            return None
        delivery_time = datetime.datetime.fromtimestamp(delivery_time_ts)
	r = ReceiveLabel.get_receive_label(delivery_time_ts-time.time())
	if country_code=='fr':
	    receive_label = r.label_fr
	else:
	    receive_label = r.label
        mes = Message(
            message=message,
            receiver_id=receiver_id,
            receiver_phone=receiver_phone,
            delivery_time=delivery_time,
            sender_id=current_user.id,
	    is_blocked=is_blocked,
            photo_id=photo_id,
	    video_id=video_id,
	    sound_id=sound_id,
            receive_label=receive_label,
            receive_color=ReceiveLabel.get_rand_color(),
            version="1.0"
        )
        mes.save()
        if receiver_phone is not None:
            bottle = Bottle(message_id=mes.id, phone_num=receiver_phone)
            bottle.save()
	else:
	    if str(receiver_id)!=str(current_user.id) and delivery_time_ts-time.time() > 200:
		u = User.objects.with_id(receiver_id)
		if u is not None and u.get_platform_instance() is not None:
		    a = AddressBook.objects(user_id=receiver_id).first()
		    if a is not None:
			plat = current_user.get_platform_instance()
			if plat is not None:
			    json_contacts = json.loads(a.on_pictever)
			    for c in json_contacts:
				if c.get('phoneNumber1')==plat.phone_num:
				    message = c.get('name')
				    r = ReceiveLabel.get_receive_label(delivery_time_ts-time.time())
				    if u.country_code=='fr':
					message+=" vient de t'envoyer un message. Tu le recevras "+r.future_label_fr+" !"
				    else:
				    	message+=" just sent you a message. You will receive it "+r.future_label+" !"
				    send_silent_notification(message,u.get_platform_instance())
				    break
        print "saved message to db"
	return mes.id

class AddressBook(db.Document):
    user_id = db.ObjectIdField(required=True)
    need_to_refresh = db.BooleanField(default=True,required=True)
    all_contacts = db.StringField(default="",required=True)
    on_pictever = db.StringField(default="",required=True)
    is_new = db.BooleanField(default=True,required=True)

class PlatformInstance(db.Document):
    """ represent one installed app on a phone 
    a User can have several of these """
    is_verified = db.BooleanField(default=False, required=True)
    verification_code = db.StringField(max_length=100, required=True)  
    phone_num = db.StringField(default="", required=True)
    os = db.StringField(max_length=255, default=None)
    app_version = db.StringField(default=None)
    reg_id = db.StringField(max_length=255, default=None)
    user_id = db.ObjectIdField(required=True)
    status = db.StringField(default="Newbie")

    def get_contact_infos(self,num) :
        try:
            infos = {}
            infos["phoneNumber1"] = num
            infos["email"] = ""
            infos["facebook_id"] = ""
            infos["facebook_name"] = ""
            infos["status"] = self.status
            infos["user_id"] = str(self.user_id)
            return infos
        except:
            return None

class Bottle(db.Document):
#    """ store a phone and a Message id corresponding to a message that was 
#    sent to someone without the app at the time"""
    message_id = db.ObjectIdField(required=True)
    phone_num = db.StringField(max_length=50, required=True)
    active = db.BooleanField(default=True)

class User(db.Document):
    email = db.StringField(required=True) 
    password_hash = db.StringField(max_length=255, required=True)
    active = db.BooleanField(default=True, required=True)
    created_at = db.DateTimeField(default=datetime.datetime.fromtimestamp(1412121600),required=True)
    platform_instance = db.ObjectIdField(default=None) 
    status = db.StringField(default="Newbie")
    verification_code = db.StringField(default="keo")
    phone_mail_sent = db.BooleanField(default=False)
    facebook_id = db.StringField(default=None) 
    facebook_name = db.StringField(default=None)
    facebook_birthday = db.StringField(default=None)
    country_code = db.StringField(default='us')
    last_log_time = db.DateTimeField(default=datetime.datetime.fromtimestamp(1412121600))

    def check_bottles(self):
        """ loop over all Bottles to check for messages already pending"""
        num = self.get_platform_instance().phone_num
        for b in Bottle.objects(active=True, phone_num=num):
            mes = Message.objects.with_id(b.message_id)
            mes.receiver_id = self.id
	    if mes.delivery_time < datetime.datetime.now():
	        mes.delivery_time = datetime.datetime.now()
	    mes.is_blocked = False
	    mes.save()
	    b.active=False
	    b.save()

#    def check_messages_in_a_bottle(self):
#        """ loop over all messages to check if the"""
#        num = self.get_platform_instance().phone_num
#        for m in Message.objects(receiver_phone=num):
#            m.receiver_id = self.id
#	    m.is_blocked = False
#	    m.save()

    def get_number_of_future_messages(self):
        """ get the number of future messages"""
	counter = 0
        for m in Message.objects(receiver_id=self.id,notif_delivered=False):
            if str(time.mktime(m.created_at.utctimetuple()))!=str(time.mktime(m.delivery_time.utctimetuple())):
	        if m.is_blocked:
		    print "message bloque ne compte pas"
		else:
	            counter += 1
	return counter
    
    def get_my_status(self):
        """ the status of the user depends on the number of messages sent - and not yet delivered - by the user in the future"""
	if self.get_platform_instance().phone_num == "0033668648212" or self.get_platform_instance().phone_num == "0033612010848":
	    return "Founder"
	else:
	    counter = 0
            for m in Message.objects(sender_id=self.id,notif_delivered=False):
		if m.delivery_time > m.created_at:
		    counter += 1
		else:
		    print "send now not counted"
	    status = Status.get_current_status(counter)
	    current_user_status = Status.objects(label=self.status).first()
	    if status.inf > current_user_status.inf:
	    	return status.label
	    else:
		return current_user_status.label

    def set_reg_id_os_and_version(self, os, reg_id,app_version):
        """ set the reg id of the first phone number ... """
        if self.platform_instance is not None:
            platform = PlatformInstance.objects.with_id(self.platform_instance)
            if reg_id is not None:
                platform.reg_id = reg_id
            else:
                raise("error no reg_id")
            platform.os = os
            platform.app_version = app_version
            platform.save()

    def get_messages_since(self, timestamp, now_ts):
        previous = datetime.datetime.fromtimestamp(timestamp)
        now = datetime.datetime.fromtimestamp(now_ts)
        messages = Message.objects(receiver_id=self.id, delivery_time__gte=previous, delivery_time__lte=now)
        print messages.count() 
        answer = []
        for m in messages:
	    if m.is_blocked==False:
                sender = User.objects.with_id(m.sender_id)
		if sender is not None:
		    if sender.get_platform_instance() is None:
		        from_numero = sender.email
		    else:
			from_numero = sender.get_platform_instance().phone_num
		    if sender.facebook_name is not None:
			facebook_id=sender.facebook_id
			facebook_name=sender.facebook_name
		    else:
			facebook_id=""
			facebook_name=""
                    d = {
		        "message_id": str(m.id),
		        "received_at": str(time.mktime(m.delivery_time.utctimetuple())),
                        "from_email": sender.email,
			"from_facebook_id": facebook_id,
			"from_facebook_name": facebook_name,
                        "from_numero": from_numero,
                        "from_id": str(sender.id), 
                        "message": m.message,
                        "created_at": str(time.mktime(m.created_at.utctimetuple())),
                        "photo_id": str(m.photo_id),
                        "video_id": str(m.video_id),
                        "sound_id": str(m.sound_id),
                        "receive_label": m.receive_label,
                        "receive_color":m.receive_color,
                        "version": m.version
                    }
                    answer.append(d)
        return answer

    def get_platform_instance(self):
        try:
            return PlatformInstance.objects.with_id(self.platform_instance)
        except:
            return None

    def is_authenticated(self):
        return True

    def is_active(self):
        return self.active
    
    def is_anonymous(self):
        """ no anonymous users for now """
        return False

    def get_id(self):
        """ we use the mongodb objectid as the id for flask-login (as a unicode)"""
        return unicode(self.id)

    def get_contact_info(self, num=None):
        infos = {}
        if num is None:
            num = PlatformInstance.objects.with_id(self.platform_instance)
        infos["phoneNumber1"] = num.phone_num
        infos["email"] = ""
	#facebook_id=""
	#facebook_name=""
	#if self.facebook_id is not None : 
	#    facebook_id=self.facebook_id
	#    facebook_name=self.facebook_name
	infos["facebook_id"] = ""
	infos["facebook_name"] = ""
	infos["status"] = self.status
        infos["user_id"] = str(self.id)
        return infos

    @staticmethod
    def get_contact_from_num(num):
        try:
            plat = PlatformInstance.objects(phone_num=num).order_by('-id').first()
            user = User.objects.with_id(plat.user_id)
            return user.get_contact_info(plat)
        except:
            return None


class Status(db.Document):
    active = db.BooleanField(default=False)
    label = db.StringField(default="",required=True)
    inf = db.IntField(required=True)
    sup = db.IntField(required=True)

    @staticmethod
    def get_current_status(my_counter):
	print str(my_counter)
	current_status=Status.objects(label="Newbie").first()
        for status in Status.objects(active=True):
            if my_counter >= status.inf and my_counter <= status.sup :
                current_status = status
        return current_status

class ReceiveLabel(db.Document):
    active = db.BooleanField(default=False)
    label = db.StringField(default="",required=True)
    label_fr = db.StringField(default="",required=True)
    future_label = db.StringField(default="",required=True)
    future_label_fr = db.StringField(default="",required=True)
    color = db.StringField(default="",required=True)
    inf = db.IntField(required=True)
    sup = db.IntField(required=True)

    @staticmethod
    def get_receive_label(counter):
	return_label = ReceiveLabel.objects().order_by('id').first()
        for r in ReceiveLabel.objects(active=True):
            if counter >= r.inf and counter <= r.sup :
       		 return r
        return return_label

    @staticmethod
    def get_rand_color():
	rand = random.randint(1,4)
	if rand==1:
	    return "ffdc1a" #jaune
	if rand==2:
	    return "6bb690" #vert
	if rand==3:
	    return "f6591e" #orange
	if rand==4:
	    return "f36f4d" #rouge

class SendChoice(db.Document):
    active = db.BooleanField(default=False)
    order_id = db.IntField(required=True)
    send_label = db.StringField(default="", required=True)
    send_label_fr = db.StringField(default="", required=True)
    receive_label = db.StringField(default="", required=True)
    receive_color = db.StringField(default="", required=True)
    key = db.StringField(required=False)
    # indicate if the time_delay is absolute (ie since 1970 UTC) or relative
    time_absolute = db.BooleanField(default=False, required=True)  
    time_random = db.BooleanField(default=False)
    #int in second for the time delay to send a message
    time_delay = db.IntField(required=False)

    @staticmethod
    def get_active_choices(country_code):
        choices = []
	if country_code=='fr':
            for choice in SendChoice.objects(active=True):
                d = {}
            	d["order_id"] = str(choice.order_id)
            	d["key"] = str(choice.id)
           	d["send_label"] = choice.send_label_fr
           	choices.append(d)
	else:
	    for choice in SendChoice.objects(active=True):
                d = {}
            	d["order_id"] = str(choice.order_id)
            	d["key"] = str(choice.id)
           	d["send_label"] = choice.send_label
           	choices.append(d)
        return choices

    @staticmethod
    def process_delivery_option(delivery_option):
        if delivery_option["type"] == "calendar":
            return int(delivery_option["parameters"])
        else:
            send_choice = SendChoice.objects.with_id(delivery_option["type"])
            return send_choice.get_delivery_time(time.time())

    def get_delivery_time(self, send_time):
        if self.time_random:
            time_delay = random.randint(5259487, 25000000)  # between 2 months and 8 months
            return send_time + time_delay
        if self.time_absolute:
            return self.time_delay
        else:
            return send_time + self.time_delay


class WebApp(db.Document):
    """ contains the url corresponding to a given version and os. """

    url = db.StringField(required=True)
    supported_version = db.ListField(default=[])

    @staticmethod
    def get_server_url_from_plateform_instance(plateform_instance=None):
        if plateform_instance is None:
            return WebApp.objects().order_by('id').first().url
        else:
            app = WebApp.objects(supported_version=plateform_instance.app_version).first() 
            if app is not None:
                return app.url
            else:
                return WebApp.objects().order_by('id').first().url





