#!/bin/python3 -Wignore

import urllib.parse, urllib.request, sys, os.path, re, json, termux, wget
from time import sleep
from geopy.geocoders import GoogleV3
from apscheduler.schedulers.background import BlockingScheduler

if not os.path.isfile("config.py"):
	sys.exit("'config.py' not found! Please add it and try again.")
else:
	import config

sched = BlockingScheduler()
ssh_username = config.SSH_USERNAME
ssh_password = config.SSH_PW
ssh_host = config.SSH_HOST
openweather_apikey = config.OPENWEATHER_API_KEY
googlegeo_apikey = config.GOOGLEGEO_API_KEY
outputdir='./output/'
telemetryfile = f'{outputdir}telemetry.txt'
wxfile = f'{outputdir}weather.txt'
iconfile = f'{outputdir}wxicon.png'
useragent = "strimpy"
#uncomment correct home directory type for streaming computer
homename = "Users"  # MacOS
# homename = "home"   # Linux
cur_dir = os.path.abspath(".")

def get_wx(args):
    cleanargs=re.sub(r'[^a-zA-Z0-9\,\. -]','', args)
    location=geocode(cleanargs)
    if "1" in location:
        print('Error in Geolocation.')
    for each in location['address_components']:
        if 'locality' in each['types']:
            locality = each['long_name']
        if 'administrative_area_level_1' in each['types']:
            state = each['long_name']
        if 'country' in each['types']:
            country = each['long_name']
    outputlocation= f"{locality}, {state}, {country}"
    url = f"https://api.openweathermap.org/data/2.5/onecall?lat={str(location['geometry']['location']['lat'])}&lon={str(location['geometry']['location']['lng'])}&exclude=minutely,hourly&appid="+openweather_apikey
    response = urllib.request.urlopen(url)
    response = json.loads(response.read().decode('utf-8'))
    try:
        tempc = round(float(response['current']['temp']-272.15),1)
        tempf = round(float(response['current']['temp']*1.8-459.67),1)
        flc = round(float(response['current']['feels_like']-272.15),1)
        flf = round(float(response['current']['feels_like']*1.8-459.67),1)
        minc = round(float(response['daily'][0]['temp']['min']-272.15),1)
        minf = round(float(response['daily'][0]['temp']['min']*1.8-459.67),1)
        maxc = round(float(response['daily'][0]['temp']['max']-272.15),1)
        maxf = round(float(response['daily'][0]['temp']['max']*1.8-459.67),1)
        windspeedms = round(float(response['current']['wind_speed']),1)
        windspeedkmh = round(windspeedms * 3.6,1)
        windspeedmph = round(windspeedms * 2.236936,1)
        winddirection = direction_from_degrees(int(response['current']['wind_deg']))
    except:
        output=f'Error fetching weather data for location {outputlocation}'
        return output,'1'
    else:
        icon=f"http://openweathermap.org/img/wn/{response['current']['weather'][0]['icon']}@2x.png"
        output=f"Current Conditions in {outputlocation}: {response['current']['weather'][0]['description'].capitalize()}\n"
        output+=f"Temperature: {tempc} °C ({tempf} °F) | "
        output+=f"Humidity: {response['current']['humidity']}%\n"
        output+=f"Daily Maximum: {maxc} °C ({maxf} °F) | "
        output+=f"Wind: {winddirection} @ {windspeedkmh} km/h ({windspeedmph} mph)"
        return output, icon

def direction_from_degrees(degrees):
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW", "N"]
    compass_direction = round(degrees / 22.5)
    return directions[compass_direction]

def geocode(location):
    geo = GoogleV3(api_key=googlegeo_apikey, user_agent=useragent)
    try:
        output = geo.geocode(location).raw
        print(f"Google geocode request for {output['formatted_address']}")
    except:
        output = {1:1}
    return output

def both():
    os.chdir(cur_dir)
    locationtuple = termux.API.location()
    locationjson = dict(locationtuple[1])
    try:
        print(locationjson)
        coords = f"{locationjson['latitude']},{locationjson['longitude']}"
        wx, icon = get_wx(coords)
        speedkmh = round(float(locationjson['speed']) * 3.6,1)
        speedmph = round(speedkmh * 2.236936,1)
        direction = direction_from_degrees(locationjson['bearing'])
        altitude = round(float(locationjson['altitude']))
        telemetry = f"Speed: {speedkmh} km/h ({speedmph} mph) | {direction} | Altitude: {altitude} m"
        if os.path.exists(iconfile):
            os.unlink(iconfile)
        wget.download(icon,out=iconfile)
        with open(telemetryfile,"w+") as telemetryoutput:
            telemetryoutput.write(telemetry)
        with open(wxfile,"w+") as wxoutput:
            wxoutput.write(wx)
        os.system(f"sshpass -p {ssh_password} scp -o StrictHostKeyChecking=no {outputdir}*.* {ssh_username}@{ssh_host}:/{homename}/{ssh_username}/strim/")
    except:
        sleep(15)
        both()

def justtelemetry():
    os.chdir(cur_dir)
    locationtuple = termux.API.location()
    locationjson = dict(locationtuple[1])
    speedkmh = round(float(locationjson['speed']) * 3.6,1)
    speedmph = round(float(locationjson['speed']) * 2.236936,1)
    direction = direction_from_degrees(locationjson['bearing'])
    altitude = round(float(locationjson['altitude']))
    telemetry = f"Speed: {speedkmh} km/h ({speedmph} mph) | {direction} | Altitude: {altitude} m"
    with open(telemetryfile,"w+") as telemetryoutput:
        telemetryoutput.write(telemetry)
    os.system(f"sshpass -p {ssh_password} scp -o StrictHostKeyChecking=no {telemetryfile} {ssh_username}@{ssh_host}:/{homename}/{ssh_username}/strim/")


def main():
    both() # initial run to get weather so we don't wait 10 minutes for first one
    wxinterval = 10 # 10 minutes
    telemetryinterval = 5 # 5 seconds
    # add jobs, getting weather every *wxinterval* minutes and getting
    # just telemetry every *telemetryinterval* secs unless already getting:
    sched.add_job(both, 'interval', minutes = wxinterval)
    sched.add_job(justtelemetry, 'interval', seconds = telemetryinterval)
    sched.start()

if __name__== "__main__":
    main()