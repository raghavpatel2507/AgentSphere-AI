from typing import Any, Optional, List
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import pickle

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

def get_authenticated_service():
    """Get authenticated YouTube API service."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def get_video_details(video_id: str) -> Optional[dict[str, Any]]:
    """Get detailed information about a video."""
    try:
        youtube = get_authenticated_service()
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            return None
            
        video = response['items'][0]
        snippet = video['snippet']
        stats = video['statistics']
        content = video['contentDetails']
        
        return {
            'id': video_id,
            'title': snippet['title'],
            'description': snippet['description'],
            'channel_id': snippet['channelId'],
            'channel_title': snippet['channelTitle'],
            'published_at': snippet['publishedAt'],
            'duration': content['duration'],
            'view_count': stats.get('viewCount', '0'),
            'like_count': stats.get('likeCount', '0'),
            'comment_count': stats.get('commentCount', '0'),
            'tags': snippet.get('tags', []),
            'thumbnails': snippet['thumbnails']
        }
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return None

def get_channel_info(channel_id: str) -> Optional[dict[str, Any]]:
    """Get information about a channel."""
    try:
        youtube = get_authenticated_service()
        request = youtube.channels().list(
            part="snippet,statistics",
            id=channel_id
        )
        response = request.execute()
        
        if not response['items']:
            return None
            
        channel = response['items'][0]
        snippet = channel['snippet']
        stats = channel['statistics']
        
        return {
            'id': channel_id,
            'title': snippet['title'],
            'description': snippet['description'],
            'subscriber_count': stats.get('subscriberCount', '0'),
            'video_count': stats.get('videoCount', '0'),
            'view_count': stats.get('viewCount', '0'),
            'thumbnails': snippet['thumbnails'],
            'published_at': snippet['publishedAt']
        }
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return None

def get_video_comments(video_id: str, max_results: int = 100) -> list[dict[str, Any]]:
    """Get comments for a video."""
    try:
        youtube = get_authenticated_service()
        comments = []
        
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            textFormat="plainText"
        )
        
        while request and len(comments) < max_results:
            response = request.execute()
            
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment['authorDisplayName'],
                    'text': comment['textDisplay'],
                    'like_count': comment['likeCount'],
                    'published_at': comment['publishedAt']
                })
                
                if len(comments) >= max_results:
                    break
            
            # Get the next page of comments
            request = youtube.commentThreads().list_next(request, response)
            
        return comments
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def get_trending_videos(region_code: str = "US", max_results: int = 50) -> list[dict[str, Any]]:
    """Get trending videos for a region."""
    try:
        youtube = get_authenticated_service()
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=min(max_results, 50)
        )
        response = request.execute()
        
        videos = []
        for item in response['items']:
            snippet = item['snippet']
            stats = item['statistics']
            videos.append({
                'id': item['id'],
                'title': snippet['title'],
                'channel_id': snippet['channelId'],
                'channel_title': snippet['channelTitle'],
                'published_at': snippet['publishedAt'],
                'view_count': stats.get('viewCount', '0'),
                'like_count': stats.get('likeCount', '0'),
                'comment_count': stats.get('commentCount', '0'),
                'thumbnails': snippet['thumbnails']
            })
        
        return videos
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def get_related_videos(video_id: str, max_results: int = 25) -> list[dict[str, Any]]:
    """Get videos related to a specific video."""
    try:
        youtube = get_authenticated_service()
        request = youtube.search().list(
            part="snippet",
            relatedToVideoId=video_id,
            type="video",
            maxResults=min(max_results, 25)
        )
        response = request.execute()
        
        videos = []
        for item in response['items']:
            snippet = item['snippet']
            videos.append({
                'id': item['id']['videoId'],
                'title': snippet['title'],
                'channel_id': snippet['channelId'],
                'channel_title': snippet['channelTitle'],
                'published_at': snippet['publishedAt'],
                'description': snippet['description'],
                'thumbnails': snippet['thumbnails']
            })
        
        return videos
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def get_video_transcript(video_id: str) -> Optional[List[dict[str, Any]]]:
    """Get the transcript for a video.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of transcript segments with text and timing information, or None if transcript is not available
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript_list
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as e:
        print(f"An error occurred while getting transcript: {e}")
        return None 