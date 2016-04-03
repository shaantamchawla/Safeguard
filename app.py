from flask import Flask, render_template, request, redirect, jsonify, url_for
from twilio.rest import TwilioRestClient
from geopy import Nominatim
import twilio.twiml
import datetime
import jinja2
import json
import os

from bson.objectid import ObjectId
import pymongo
from pymongo import MongoClient

account_sid = "ACf1377bb16eefa80d9e68de47e591e570"
auth_token = "45166aed5806737d6451d16ae7c4f44f"
twilioClient = TwilioRestClient(account_sid, auth_token)

app = Flask(__name__)

client = MongoClient()
db = client.test_db
locations = db.locations
people = db.people

geolocator = Nominatim()
threats_dict = {1: "Active Shooter", 2: "Explosion", 3: "Biohazard", 4: "Gas Leakage", 5: "Severe Weather"}

#Home page - the map of logged security threats
@app.route('/', methods=['GET', 'POST'])
def index():
	latlongs = []

	for item in locations.find():
		item['_id'] = str(item['_id'])
		latlongs.append({'latLng': [item['latitude'], item['longitude']], 
			'name': item['city'] + ", " + item['state'] + "; " + item['datestr'] + "; " + threats_dict[item['threat']],
			'city': item['city'],
			'state': item['state']})

	return render_template("index.html", coords=json.dumps(latlongs))

#Process an SMS from a user "check-in" - store it in the database and send everyone in that location a warning
@app.route('/sms', methods=['GET', 'POST'])
def receive_sms():
	msg_body = request.values.get('Body', None).lower().strip()
	threat = 0

	if ("shoot" in msg_body or "gun" in msg_body):
		threat = 1
		threat_text = " an active shooter "

	elif ("explosion" in msg_body or "fire" in msg_body):
		threat = 2
		threat_text = " an explosion "

	elif ("bio" in msg_body or "chemical" in msg_body):
		threat = 3
		threat_text = " a biohazard "

	elif ("gas" in msg_body or "leak" in msg_body):
		threat = 4
		threat_text = " a gas leak "

	elif ("hurricane" in msg_body or "tornado" in msg_body or "flood" in msg_body):
		threat = 5
		threat_text = " a severe weather warning "

	city = request.values.get('FromCity', None)
	state = request.values.get('FromState', None)
	zipcode = request.values.get('FromZip', None)

	location_string = city + ", " + state + " " + zipcode
	print(location_string)
	location = geolocator.geocode(location_string)
	latitude = location.latitude
	longitude = location.longitude

	data_point = {'zipcode': zipcode,
		'city': city,
		'state': state,
		'latitude': latitude, 
		'longitude': longitude,
		'datestr': datetime.datetime.now().strftime("%A %B %d, %Y %I:%M %p"),
		'threat': threat
	}

	locations.insert(data_point)
	#locations.insert({'zipcode': 75201, 'city': 'Dallas', 'state': 'TX', 'latitude': 32.77, 'longitude': -96.797, 'threat': 2, 'datestr': 'Sunday April 03, 2016 06:26 AM'})
	#locations.insert({'zipcode': 77014, 'city': 'Houston', 'state': 'TX', 'latitude': 29.7604, 'longitude': -95.367, 'threat': 4, 'datestr': 'Sunday April 03, 2016 01:48 AM'})
	#locations.insert({'zipcode': 85006, 'city': 'Phoenix', 'state': 'AZ', 'latitude': 33.45, 'longitude': -112.074, 'threat': 3, 'datestr': 'Tuesday March 29, 2016 02:52 PM'})
	#locations.insert({'zipcode': 02118, 'city': 'Boston', 'state': 'MA', 'latitude': 42.36, 'longitude': -71.06, 'threat': 5, 'datestr': 'Wednesday March 23, 2016 04:22 PM'})
	#locations.insert({'zipcode': 15211, 'city': 'Pittsburgh', 'state': 'PA', 'latitude': 40.44, 'longitude': -80, 'threat': 3, 'datestr': 'Friday March 25, 2016 12:40 AM'})
	#locations.insert({'zipcode': 77014, 'city': 'Houston', 'state': 'TX', 'latitude': 29.7604, 'longitude': -95.367, 'threat': 1, 'datestr': 'Saturday April 02, 2016 03:09 PM'})
	#locations.insert({'zipcode': 80207, 'city': 'Denver', 'state': 'CO', 'latitude': 39.739, 'longitude': -105, 'threat': 2, 'datestr': 'Friday April 01, 2016 02:29 PM'})
	#locations.insert({'zipcode': 62716, 'city': 'Springfield', 'state': 'IL', 'latitude': 39.78, 'longitude': -89.65, 'threat': 3, 'datestr': 'Friday Mrch 25, 2016 06:14 PM'})

	for person in people.find():
		if (zipcode == person['zipcode']):
			twilioClient.messages.create(to=("+1" + str(person['phone_num'])), from_="2013899077", body=("There has been" + threat_text + "recently reported in your area."))

	print(msg_body)
	return('SUCCESS')

@app.route('/register', methods=['GET','POST'])
def register():
	if request.method == 'POST':
		phone_num = request.form['phone_num']
		zipcode = request.form['zipcode']

		person = {'phone_num': phone_num,
			'zipcode': zipcode
		}

		people.insert(person)

		return redirect('/')
	
	return render_template('register.html')

@app.route('/view', methods=['GET'])
def view():
	city_list = {}
	top_nums = []
	for location in locations.find():
		curr_city = location['city']
		if curr_city in city_list:
			city_list[curr_city] += 1
		else:
			city_list[curr_city] = 1

		print(city_list)

	top_cities = sorted(city_list, key=city_list.get, reverse=True)[:5]
	for city in top_cities:
		top_nums.append(city_list[city])

	num_incidents = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
	types = ['Active Shooter', 'Explosion', 'Biohazard', 'Gas Leakage', 'Severe Weather']
	for location in locations.find():
		num_incidents[location['threat']] += 1

	return render_template('view.html', top_cities=top_cities, top_nums=top_nums, num_incidents=num_incidents, types=types)

if __name__ == '__main__':
	app.run(debug=True)