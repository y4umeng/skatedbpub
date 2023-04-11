SkateDB: Skateboard social media application using Python, Flask, PostgreSQL, and Werkzeug


Users can register, log in, and log out, with encrypted password protection. Users can follow and unfollow each other. Users can be granted moderator privileges. Users can browse recent tricks and spots, as well as search through the database with the search form. They can post tricks and spots, with nearly all the data we originally mentioned such as trick type, spot location (latitude and longitude), skater name, video link etc. All this data is stored in the trick and spot tables. Once a trick or spot is posted, other users can view it. If a user is a moderator they have the ability to verify tricks or spots. Furthermore users can post events which occur at spots. They can also browse events posted by other users on the events page.


 

Implementing the keyword search was cool. It was fun playing around with the ts_query and ts_vector to get the optimal search functionality. Full text search is used with data on tricks and spots to allow users to query all the tricks and spots with search terms. Currently only prefix and full word matches work, as psql FTS is pretty bare bones in terms of text search. 



