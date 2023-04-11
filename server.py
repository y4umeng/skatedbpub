
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, url_for, flash
import psycopg2
import psycopg2.extras
import re
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, render_template, g, redirect, Response, Markup
from datetime import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

app.secret_key = b''

DATABASE_USERNAME = ""
DATABASE_PASSWRD = ""
DATABASE_HOST = "" 
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/project1"

engine = create_engine(DATABASEURI)

with engine.connect() as conn:
	pass

@app.before_request
def before_request():
	"""
	This function is run at the beginning of every web request 
	(every time you enter an address in the web browser).
	We use it to setup a database connection that can be used throughout the request.

	The variable g is globally accessible.
	"""
	try:
		g.conn = engine.connect()
	except:
		print("uh oh, problem connecting to database")
		import traceback; traceback.print_exc()
		g.conn = None

@app.teardown_request
def teardown_request(exception):

	"""
	At the end of the web request, this makes sure to close the database connection.
	If you don't, the database could run out of memory!
	"""
	try:
		g.conn.close()
	except Exception as e:
		pass
	
def getTricks(poster, spot, skater, link, keywords):
	trick_ids = []
	trick_descs = []
	trick_times = []
	skaters = []
	spots = []
	posters = []
	links = []
	posts_query = """
		SELECT trick_id, trick_desc, trick_time, skater, spot, username, link
		FROM (SELECT * FROM trick ORDER BY trick_time LIMIT 100) as t, profile
		WHERE poster_ID = user_ID
		"""
	if poster:
		posts_query = posts_query + f" AND user_id = :poster"
	if spot:
		posts_query = posts_query + f" AND spot = :spot"
	if skater:
		posts_query = posts_query + f" AND skater = :skater"
	if link:
		posts_query = posts_query + f" AND link = :link"	
	if keywords:
		posts_query = posts_query + f"""
		AND to_tsvector(trick_desc || ' ' || skater || ' ' || spot || ' ' || username) 
		@@ to_tsquery('english', :keywords)
		"""
	input = {
		"poster": poster,
		"spot": spot,
		"skater": skater,
		"link": link,
		"keywords": keywords
	}
	cursor = g.conn.execute(text(posts_query), input)
	for result in cursor:
		trick_ids.append(result[0])
		trick_descs.append(result[1])
		trick_times.append(result[2])
		skaters.append(result[3])
		spots.append(result[4])
		posters.append(result[5])
		links.append(result[6])
	cursor.close()
	posts = zip(trick_ids, trick_descs, trick_times, skaters, spots, posters, links)
	return {"posts": posts}

@app.route('/')
def index():
	if 'username' in session:
		return redirect(url_for('feed'))
	return redirect(url_for('login'))

@app.route('/feed')
def feed():
	if 'username' not in session:
		return redirect(url_for('login'))
	return render_template("feed.html", **getTricks("", "", "", "", "")) 

@app.route('/submit_spot', methods=['GET', 'POST'])
def submit_spot():
	if 'username' not in session:
		return redirect(url_for('login'))
	
	if request.method == 'POST' and 'spot' in request.form and 'lat' in request.form and 'lon' in request.form and 'desc' in request.form:
		spot = " ".join(request.form['spot'].split())
		lat = request.form['lat']
		lon = request.form['lon']
		desc = request.form['desc'].strip()
		input = {
			'spot': spot,
			'desc': desc,
			'id': session['id'],
			'lat': lat,
			'lon': lon
		}
		if not (spot and lat and lon and desc):
			flash("please fill out the entire form")
			return render_template('submit_spot.html')
		if g.conn.execute(text(f"SELECT * FROM spot WHERE LOWER(spot)=LOWER(:spot)"), input).fetchone(): 
			flash("A spot with this name already exists in the database")
			return render_template('submit_spot.html')	
		
		# regex from https://stackoverflow.com/questions/3518504/regular-expression-for-matching-latitude-longitude-coordinates
		if not re.match(r"^(\+|-)?(?:90(?:(?:\.0{1,20})?)|(?:[0-9]|[1-8][0-9])(?:(?:\.[0-9]{1,20})?))$", lat):
			flash("invalid latitude")
			return render_template('submit_spot.html')
		if not re.match(r"^(\+|-)?(?:180(?:(?:\.0{1,20})?)|(?:[0-9]|[1-9][0-9]|1[0-7][0-9])(?:(?:\.[0-9]{1,20})?))$", lon):
			flash("invalid longitude")
			return render_template('submit_spot.html')
		if len(desc) > 1000:
			flash("description too long")
			return render_template('submit_spot.html')
		submit_query = 'INSERT INTO spot(spot, description, poster_id, location) VALUES (LOWER(:spot), :desc, :id, point(:lat, :lon))'  
		g.conn.execute(text(submit_query), input)
		g.conn.commit()
		return redirect(url_for("feed"))
	return render_template('submit_spot.html')	

# Example of adding new data to the database
@app.route('/submit', methods=['GET', 'POST'])
def submit():
	if 'username' not in session:
		return redirect(url_for('login'))
	if request.method == 'POST' and 'desc' in request.form and 'skater' in request.form and 'spot' in request.form and 'link' in request.form and 'timestamp' in request.form:	
		desc = request.form['desc'].strip()
		skater = " ".join(request.form['skater'].split())
		spot = " ".join(request.form['spot'].split())
		link = request.form['link'].strip()
		timestamp = request.form['timestamp'].strip()
		input = {
			"desc": desc,
			"skater": skater,
			"spot": spot,
			"link": link,
			"timestamp": timestamp
		}
		if not (desc and skater and spot and link and timestamp):
			flash("please fill out the entire form")
			return render_template('submit.html')
		if len(desc) >= 1000:
			flash("description too long")
			return render_template('submit.html')
		if not re.match(r"^(([0-9]*)m(([0-9])|([0-5][0-9]))s)$", timestamp):
			flash("timestamp in wrong form. please use xxmxxs (ex. 1m23s)")
			return render_template('submit.html')
		if not re.match(r"(?:https?:\/\/)?(?:youtu\.be\/|(?:www\.|m\.)?youtube\.com\/(?:watch|v|embed)(?:\.php)?(?:\?.*v=|\/))([a-zA-Z0-9\_-]+)", link):
			flash("please provide a valid youtube link")
			return render_template('submit.html')
		if len(skater) > 255:
			flash("skater name too long")
			return render_template('submit.html')
		if len(spot) > 255:
			flash("spot name too long")	
			return render_template('submit.html')
		result = g.conn.execute(text(f"SELECT spot FROM spot WHERE LOWER(spot)=LOWER(:spot)"), input).fetchone() 
		if not result:
			flash("spot doesn't exist in the database. please submit the spot on the spots page before submitting the trick")
			return render_template('submit.html')
		else:
			input['spot'] = result[0]
		print(input['spot'])
		submit_query = f"""
			INSERT INTO trick(trick_desc, trick_time, poster_id, timestamp, link, skater, spot) 
			VALUES (:desc, now(), {session['id']}, :timestamp, :link, :skater, :spot)""" 
		g.conn.execute(text(submit_query), input)
		g.conn.commit()
		return redirect(url_for("feed"))
	return render_template('submit.html')

@app.route('/event', methods=['GET', 'POST'])
def event():
	if 'username' not in session:
		return redirect(url_for('login'))
	if request.method == 'POST' and 'name' in request.form and 'desc' in request.form and 'spot' in request.form and 'date' in request.form:
		desc = request.form['desc'].strip()
		name = " ".join(request.form['name'].split())
		spot = " ".join(request.form['spot'].split())
		date = request.form['date'].strip()
		print(spot)
		if not (desc and spot and name and date):
			flash("please fill out the entire form")
			return redirect(url_for('event')) 
		if len(desc) > 1000:
			flash("description too long")
			return redirect(url_for('event'))
		# to do
		if len(name) > 255:
			flash("name too long")
			return redirect(url_for('event'))
		if len(spot) > 255:
			flash("spot name too long")	
			return redirect(url_for('event'))
		result = g.conn.execute(text(f"SELECT spot FROM spot WHERE LOWER(spot)=LOWER(:spot)"), {"spot":spot}).fetchone()	
		if not result:
			flash("spot doesn't exist in the database. please submit the spot on the spots page before submitting the trick")
			return redirect(url_for('event'))
		else:
			spot = result[0]
		
		input = {
			"spot": spot,
			"desc": desc,
			"name": name,
			"date": date
		}

		insert_event = f"""
			INSERT INTO event (event_name, description, spot, event_time, poster_id)
			VALUES (:name, :desc, :spot, :date, {session['id']})
		"""
		g.conn.execute(text(insert_event), input)
		g.conn.commit()
		return redirect(url_for('event'))
	
	events_query = """
		SELECT event_name, description, spot, event_time, username
		FROM event, profile
		WHERE user_id = poster_id and event_time >= now()
		ORDER BY event_time
		LIMIT 100
	"""
	cursor = g.conn.execute(text(events_query))
	names=[] 
	descs = []
	spots = [] 
	dates = [] 
	posters = []
	for r in cursor:
		names.append(r[0])
		descs.append(r[1])
		spots.append(r[2])
		dates.append(r[3])
		posters.append(r[4])
	events = zip(names, descs, spots, dates, posters)
	context = {"events": events}
	return render_template('event.html', **context)	

@app.route('/spot')
def spot():
	if 'loggedin' not in session:
		return redirect(url_for('login'))
	if "id" not in request.args:
		redirect(url_for("feed"))
	id = request.args['id']
	id.replace("%20", " ")
	spot_query = f"SELECT spot, description, location, username, verifier_id FROM spot, profile WHERE spot=:id and poster_ID=user_ID"
	cursor = g.conn.execute(text(spot_query), {"id":id})
	spot_data = list(cursor.fetchone())
	context = getTricks("", id, "", "", "")
	cursor.close()
	context["spot_name"] = spot_data[0]
	context["spot_desc"] = spot_data[1]
	context["lat"] = spot_data[2][1:spot_data[2].index(',')]
	context["lon"] = spot_data[2][spot_data[2].index(',') + 1:-1]
	context["spot_poster_username"] = spot_data[3]
	context["verifier"] = spot_data[4]
	if not spot_data[4] and g.conn.execute(text("SELECT * FROM moderator WHERE user_id = :ID"), {"ID": session['id']}).fetchone():
		flash(Markup(f"""<h1><a href = "/verify_spot?id={id}"> <small>verify</small></a></h1>"""))
	return render_template("spot.html", **context)	

@app.route('/trick')
def trick():
	if 'loggedin' not in session:
		return redirect(url_for('login'))
	id = request.args['id']

	trick_query = f"""
		SELECT trick_desc, trick_time, skater, spot, link, username, verifier_id
		FROM (SELECT * FROM trick WHERE trick_id = :id) as t, profile
		WHERE poster_ID = profile.user_ID
	"""	
	cursor = g.conn.execute(text(trick_query), {"id":id})
	trick_data = list(cursor.fetchone())

	cursor.close()
	context = {
		"desc": trick_data[0],
		"time": trick_data[1].strftime('%m/%d/%Y'),
		"skater": trick_data[2],
		"spot": trick_data[3],
		"link": trick_data[4],
		"poster": trick_data[5],
		"verifier": trick_data[6],
		"id": id
	}

	if not trick_data[6] and g.conn.execute(text("SELECT * FROM moderator WHERE user_id = :ID"), {"ID": session['id']}).fetchone():
		flash(Markup(f"""<h1><a href = "/verify_trick?id={id}"> <small>verify</small></a></h1>"""))
	return render_template("trick.html", **context)

@app.route('/verify_trick')
def verify_trick():
	id = request.args['id']
	if not g.conn.execute(text("SELECT * FROM moderator WHERE user_id = :ID"), {"ID": session['id']}).fetchone():
		flash("You are not a mod. boss up")
		return redirect(url_for("trick", id=id)) 
	if g.conn.execute(text("SELECT verifier_id FROM trick WHERE trick_id=:id"), {"id": id}).fetchone()[0]:
		flash("trick is already verified")
		return redirect(url_for("trick", id=id))
	
	verify_query = """
		UPDATE trick
		SET verifier_id = :verifier
		WHERE trick_id = :id
	"""
	g.conn.execute(text(verify_query), {"id": id, "verifier": session['id']})
	g.conn.commit()
	return redirect(url_for("trick", id=id))

@app.route('/verify_spot')
def verify_spot():
	id = request.args['id']
	print(id)
	if not g.conn.execute(text("SELECT * FROM moderator WHERE user_id = :ID"), {"ID": session['id']}).fetchone():
		flash("You are not a mod. boss up")
		return redirect(url_for("trick", id=id)) 
	if g.conn.execute(text("SELECT verifier_id FROM spot WHERE spot=:id"), {"id": id}).fetchone()[0]:
		flash("trick is already verified")
		return redirect(url_for("spot", id=id))
	
	verify_query = """
		UPDATE spot
		SET verifier_id = :verifier
		WHERE spot = :id
	"""
	g.conn.execute(text(verify_query), {"id": id, "verifier": session['id']})
	g.conn.commit()
	return redirect(url_for("spot", id=id))


@app.route('/search')
def search():
	if 'loggedin' not in session:
		return redirect(url_for('login'))
	keywords = request.args['terms']
	keywords = re.sub('[^0-9a-zA-Z]+', ' ', keywords).strip()
	if keywords:
		terms = keywords.split()
		keywords = ":* & ".join(terms) + ":*"

	spots = []
	spots_query = f"""
		SELECT DISTINCT spot
		FROM spot
		WHERE to_tsvector(spot) @@ to_tsquery('english', :keywords)
	"""

	# skaters = []
	# spaters_query = f"""
	# 	SELECT DISTINCT 
	# 	FROM spot
	# 	WHERE to_tsvector(spot) @@ to_tsquery('english', '{keywords}')
	# """

	cursor = g.conn.execute(text(spots_query), {"keywords":keywords})
	for r in cursor:
		spots.append(r[0])
	context = getTricks("", "", "", "", keywords)
	context['spots'] = spots

	return render_template("search.html", **context)

@app.route('/login/', methods=['GET', 'POST'])
def login():
	if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
		username = request.form['username']
		password = request.form['password']
		profile_query = f"SELECT * FROM profile WHERE username = :username" 
		cursor = g.conn.execute(text(profile_query), {"username":username}) 
		account = cursor.fetchone()
		print(account)
		# if real account
		if account:
			password_rs = account[4]
			if check_password_hash(password_rs, password):
				session['loggedin'] = True
				session['id'] = account[0]
				session['username'] = account[1]
				if g.conn.execute(text(f"SELECT * FROM moderator WHERE user_id = :id"), {"id": account[0]}).fetchone():
					session['mod'] = True
				else:
					session['mod'] = False
				return redirect(url_for('index'))
			else:
				flash('Incorrect username/password')
		else:
			flash('Incorrect username/password')
	return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
		username = request.form['username']
		password = request.form['password']
		email = request.form['email']

		_hashed_password = generate_password_hash(password)
		profile_query = f"SELECT * FROM profile WHERE username = :username" 
		cursor = g.conn.execute(text(profile_query), {"username": username}) 
		account = cursor.fetchone()
		print(account)

		if account:
			flash('That username is taken')
		elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
			flash('Invalid email address!')	
		elif not re.match(r'[A-Za-z0-9]+', username):
			flash('Username must contain only characters and numbers!')
		elif not username or not password or not email:
			flash('Please fill out the form!')
		else:
            # Account doesnt exists and the form data is valid, now insert new account into users table
			insert_query = f"""
				INSERT INTO profile(username, email, date_created, password) 
				VALUES (:username, :email, now(), :pass)	
			"""
			g.conn.execute(text(insert_query), {"username": username, "email":email, "pass":_hashed_password})
			g.conn.commit()	
			flash('You have successfully registered!')
	elif request.method == 'POST':
		flash('Please fill out the form!')
	return render_template("register.html")

@app.route('/logout')
def logout():
	session.pop('loggedin', None)
	session.pop('id', None)
	session.pop('username', None)
	return redirect(url_for('login'))

@app.route('/profile')
def profile(): 
	if "id" not in request.args:
		return redirect(url_for('feed'))
	username = request.args['id']
	if 'loggedin' not in session:
		return redirect(url_for('login'))

	profile_query = f"""SELECT * FROM profile WHERE username=:username"""	
	cursor = g.conn.execute(text(profile_query), {"username": username})	
	profile_data = list(cursor.fetchone())

	following = []
	followers = []
	context = getTricks(profile_data[0], "", "", "", "")

	following_query = f"""SELECT following FROM follows WHERE followed_by=:username"""
	followed_by_query = f"""SELECT followed_by FROM follows WHERE following=:username"""
	cursor = g.conn.execute(text(following_query), {"username": username})	
	for f in cursor:
		following.append(f[0])
	cursor = g.conn.execute(text(followed_by_query), {"username": username})
	for f in cursor:
		followers.append(f[0])		
	cursor.close
	context['following'] = following
	context['followers'] = followers
	context['username'] = username
	context['date_created'] = profile_data[3].strftime('%m/%d/%Y')
	context['id'] = username

	return render_template('profile.html', **context)

@app.route('/follow')
def follow():
	user = request.args['id']
	follow_query = f"""
		INSERT INTO follows(following, followed_by) 
		VALUES (:user, :session)
		ON CONFLICT (following, followed_by) DO NOTHING
		"""
	g.conn.execute(text(follow_query), {"user": user, "session": session['username']})
	g.conn.commit()
	return redirect(url_for('profile', id=user))

@app.route('/unfollow')
def unfollow():  
	user = request.args['id']
	follow_query = f"""DELETE FROM follows WHERE following = :user AND followed_by = :session"""
	g.conn.execute(text(follow_query), {"user": user, "session": session['username']})
	g.conn.commit()
	return redirect(url_for('profile', id=user))

if __name__ == "__main__":
	import click
	@click.command()
	@click.option('--debug', is_flag=True)
	@click.option('--threaded', is_flag=True)
	@click.argument('HOST', default='0.0.0.0')
	@click.argument('PORT', default=8111, type=int)
	def run(debug, threaded, host, port):
		HOST, PORT = host, port
		print("running on %s:%d" % (HOST, PORT))
		app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)
run()
