################################################################################
# THIS SECTION IS ALL YOU WILL HAVE TO CHANGE
################################################################################

# add in these details after getting credentials from spotify
client_id = 'XXXXXXXXXXXXXXXXXXXXXXXX'
client_secret = 'XXXXXXXXXXXXXXXXXXXXXX'
redirect_url = 'http://127.0.0.1:8080/'


playlist_url_list = [
	'https://open.spotify.com/playlist/48kgn15Mrg6XC859pVtZj5?si=c126cecc8ec84509', #guardian 
	'https://open.spotify.com/playlist/4NzWle6sDBwHLQ1tuqLKhp?si=35de4c9a61e049cd', #nme
	# Put the urls of the playlists you want to 'aggregate' here, one below the other
]

# this is the playlist where all the tracks get collected
final_playlist_url = 'https://open.spotify.com/playlist/XXXXXXXXXX?si=XXXXXXXXXXXXXXXXX'




###############################################################################
# YOU CAN IGNORE EVERYTHING BELOW THIS LINE, IT'S JUST THE CODE 
################################################################################

from spotipy.oauth2 import SpotifyOAuth
import spotipy
import time
import re
from datetime import datetime, timedelta, timezone

scope = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"
sp = spotipy.Spotify(
		auth_manager=SpotifyOAuth(
						client_id= client_id,
						client_secret= client_secret,
						redirect_uri= redirect_url,
						scope=scope,
						open_browser=False
					),
		requests_timeout=30,
		retries=5,
		backoff_factor=2.0
	)


def count_playlist_tracks(sp, playlist_id, market='US', delay=5):
	"""Count and return all tracks in a playlist."""
	results = sp.playlist_items(playlist_id, offset=0, market=market)
	items = results['items']
	while results['next']:
		time.sleep(delay)
		results = sp.next(results)
		items.extend(results['items'])
	return items


def remove_oldest_tracks_v2(sp, playlist_id, items, max_tracks=9500, batch_size=50):
	"""
	Remove the oldest tracks from a playlist if it's getting full.
	
	Args:
		sp: Spotify client
		playlist_id: ID of the playlist
		items: List of playlist items (from count_playlist_tracks) - newest first
		max_tracks: Maximum number of tracks to keep in playlist
		batch_size: Number of tracks to remove in each batch (Spotify API limit is 100)
	"""
	current_count = len(items)
	
	if current_count <= max_tracks:
		return
	
	# Calculate how many tracks we need to remove
	tracks_to_remove = current_count - max_tracks	
	
	# Get the oldest tracks (last items in playlist, assuming newest items are at top)
	oldest_items = items[:-tracks_to_remove]
	
	# Extract track IDs, handling potential None values
	track_ids_to_remove = []
	for item in oldest_items:
		if item and item['track'] and item['track']['id']:
			track_ids_to_remove.append(item['track']['id'])
	
	if not track_ids_to_remove:
		return
	
	# Remove tracks in batches (Spotify API allows max 100 tracks per request)
	for i in range(0, len(track_ids_to_remove), batch_size):
		batch = track_ids_to_remove[i:i + batch_size]
		try:
			sp.playlist_remove_all_occurrences_of_items(playlist_id, batch)
		except Exception as e:
			print(f"Error removing batch: {e}")

final_playlist_id = re.search(r'playlist/([A-Za-z0-9]+)', final_playlist_url).group(1)

# Count tracks in playlist
items_remaining_list = count_playlist_tracks(sp, final_playlist_id)

# Remove oldest tracks if the playlist is getting full, anything older than the 9,500th track gets removed
remove_oldest_tracks_v2(sp, final_playlist_id, items_remaining_list, max_tracks=9500, batch_size=50)

def previous_saturday_midnight_utc():
	now = datetime.now(timezone.utc)
	days_ago = ((now.weekday() - 5) % 7) or 7
	sat_date = (now - timedelta(days=days_ago)).date()
	return datetime.combine(sat_date, datetime.min.time(), tzinfo=timezone.utc)

last_saturday_midnight = previous_saturday_midnight_utc()

ids_to_add = []
for playlist_url in playlist_url_list:
	playlist_id = re.search(r'playlist/([A-Za-z0-9]+)', playlist_url).group(1)
	results = sp.playlist_items(playlist_id, offset=0, market='US')
	items = results['items']
	while results['next']:
		time.sleep(12)
		results = sp.next(results)
		items.extend(results['items'])

	for item in items:
		if item['track']:
			episode_boolean = item['track']['episode']
			if episode_boolean:
				continue
			track_id = item['track']['id']

			date_added_to_playlist = item['added_at'] # "2015-01-15T12:39:22Z"
			added_at_dt = datetime.fromisoformat(date_added_to_playlist.replace('Z', '+00:00'))

			if added_at_dt < last_saturday_midnight:
				continue

			if track_id not in ids_to_add:
				ids_to_add.append(track_id)


ids_to_add.reverse()

# Add tracks in batches of 100 (Spotify API limit)
for i in range(0, len(ids_to_add), 100):
	batch = ids_to_add[i:i+100]
	
	# Reverse the batch to maintain original order when added at position 0
	batch.reverse()
	
	try:
		sp.playlist_add_items(final_playlist_id, batch, position=0)
		time.sleep(8)
	except Exception as e:
		print(f"Error adding tracks to playlist: {e}")

print('script done')