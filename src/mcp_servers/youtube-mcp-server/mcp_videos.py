from typing import Any, List, Dict, Tuple, Optional
import random
import re
from dataclasses import dataclass
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from yt_helper import construct_video_url, search_youtube
from youtube_api import (
    get_video_details,
    get_channel_info,
    get_video_comments,
    get_trending_videos,
    get_related_videos,
    get_video_transcript,
)

# Initialize FastMCP server
mcp = FastMCP("videos")


def format_video(video: dict[str, Any]) -> str:
    """Format a video feature into a readable string."""
    return f"""
        Title: {video.get("title", "Unknown")}
        Channel: {video.get("channel_title", video.get("channel", "Unknown"))}
        Duration: {video.get("duration", "Unknown")}
        Description: {video.get("description", "No description available")}
        Views: {video.get("view_count", video.get("views", "Unknown"))}
        Likes: {video.get("like_count", "Unknown")}
        Comments: {video.get("comment_count", "Unknown")}
        URL: {construct_video_url(video.get("id", "dQw4w9WgXcQ"))}
        Published: {video.get("published_at", video.get("publish_time", "Unknown"))}
       """


def format_channel(channel: dict[str, Any]) -> str:
    """Format a channel feature into a readable string."""
    return f"""
        Channel Name: {channel.get("title", "Unknown")}
        Subscribers: {channel.get("subscriber_count", "Unknown")}
        Total Videos: {channel.get("video_count", "Unknown")}
        Total Views: {channel.get("view_count", "Unknown")}
        Description: {channel.get("description", "No description available")}
        Created: {channel.get("published_at", "Unknown")}
       """


def format_comment(comment: dict[str, Any]) -> str:
    """Format a comment into a readable string."""
    return f"""
        Author: {comment.get("author", "Unknown")}
        Text: {comment.get("text", "No text available")}
        Likes: {comment.get("like_count", "0")}
        Posted: {comment.get("published_at", "Unknown")}
       """


@mcp.tool()
async def get_videos(search: str, max_results: int) -> str:
    """Get videos for a search query.

    Args:
        search: Search query string
        max_results: Maximum number of results to return
    """
    results = search_youtube(search, max_results=max_results)
    if not results:
        return "No videos found."

    videos = [format_video(video) for video in results]
    return "\n---\n".join(videos)


@mcp.tool()
async def get_video_info(video_id: str) -> str:
    """Get detailed information about a video.

    Args:
        video_id: YouTube video ID
    """
    video = get_video_details(video_id)
    if not video:
        return "No video found."
    return format_video(video)


@mcp.tool()
async def get_channel_details(channel_id: str) -> str:
    """Get detailed information about a YouTube channel.

    Args:
        channel_id: YouTube channel ID
    """
    channel = get_channel_info(channel_id)
    if not channel:
        return "No channel found."
    return format_channel(channel)


@mcp.tool()
async def get_video_comments_tool(video_id: str, max_results: int = 100) -> str:
    """Get comments for a video.

    Args:
        video_id: YouTube video ID
        max_results: Maximum number of comments to return (default: 100)
    """
    comments = get_video_comments(video_id, max_results=max_results)
    if not comments:
        return "No comments found or comments are disabled."
    
    formatted_comments = [format_comment(comment) for comment in comments]
    return "\n---\n".join(formatted_comments)


@mcp.tool()
async def get_trending_videos_tool(region_code: str = "US", max_results: int = 50) -> str:
    """Get trending videos for a region.

    Args:
        region_code: Two-letter ISO country code (default: "US")
        max_results: Maximum number of videos to return (default: 50)
    """
    videos = get_trending_videos(region_code, max_results=max_results)
    if not videos:
        return "No trending videos found."
    
    formatted_videos = [format_video(video) for video in videos]
    return "\n---\n".join(formatted_videos)


@mcp.tool()
async def get_related_videos_tool(video_id: str, max_results: int = 25) -> str:
    """Get videos related to a specific video.

    Args:
        video_id: YouTube video ID
        max_results: Maximum number of videos to return (default: 25)
    """
    videos = get_related_videos(video_id, max_results=max_results)
    if not videos:
        return "No related videos found."
    
    formatted_videos = [format_video(video) for video in videos]
    return "\n---\n".join(formatted_videos)


@mcp.tool()
async def summarize_video(video_id: str, include_comments: bool = True) -> str:
    """Get a comprehensive summary of a YouTube video.
    
    Args:
        video_id: YouTube video ID
        include_comments: Whether to include top comments in the summary (default: True)
    """
    # Get video details
    video = get_video_details(video_id)
    if not video:
        return "No video found."
    
    # Get transcript
    transcript = get_video_transcript(video_id)
    
    # Get comments if requested
    comments = []
    if include_comments:
        comments = get_video_comments(video_id, max_results=5)
    
    # Build the summary
    summary = []
    
    # Add video metadata
    summary.append("=== Video Summary ===")
    summary.append(f"Title: {video['title']}")
    summary.append(f"Channel: {video['channel_title']}")
    summary.append(f"Duration: {video['duration']}")
    summary.append(f"Views: {video['view_count']}")
    summary.append(f"Likes: {video['like_count']}")
    summary.append(f"Published: {video['published_at']}")
    summary.append(f"URL: {construct_video_url(video_id)}")
    
    # Add description
    if video.get('description'):
        summary.append("\n=== Description ===")
        summary.append(video['description'])
    
    # Add transcript summary if available
    if transcript:
        summary.append("\n=== Transcript Summary ===")
        # Combine transcript segments into a single text
        full_transcript = " ".join(segment['text'] for segment in transcript)
        # Take first 500 characters as a preview
        transcript_preview = full_transcript[:500] + "..." if len(full_transcript) > 500 else full_transcript
        summary.append(transcript_preview)
    else:
        summary.append("\n=== Transcript ===")
        summary.append("No transcript available for this video.")
    
    # Add top comments if requested
    if include_comments and comments:
        summary.append("\n=== Top Comments ===")
        for comment in comments:
            summary.append(f"\n{comment['author']}:")
            summary.append(comment['text'])
            summary.append(f"Likes: {comment['like_count']}")
    
    return "\n".join(summary)


def generate_quiz_questions(video_info: dict[str, Any], transcript: Optional[List[dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Generate quiz questions from video information and transcript.
    
    Args:
        video_info: Dictionary containing video details
        transcript: List of transcript segments or None
        
    Returns:
        List of quiz questions with their answers
    """
    questions = []
    
    # Helper function to create a multiple choice question
    def create_multiple_choice(question: str, correct_answer: str, wrong_answers: List[str]) -> Dict[str, Any]:
        answers = [correct_answer] + wrong_answers
        random.shuffle(answers)
        return {
            "type": "multiple_choice",
            "question": question,
            "options": answers,
            "correct_answer": correct_answer
        }
    
    # Helper function to create a true/false question
    def create_true_false(statement: str, is_true: bool) -> Dict[str, Any]:
        return {
            "type": "true_false",
            "question": statement,
            "correct_answer": "True" if is_true else "False"
        }
    
    # Helper function to create a fill in the blank question
    def create_fill_blank(question: str, answer: str) -> Dict[str, Any]:
        return {
            "type": "fill_blank",
            "question": question,
            "correct_answer": answer
        }
    
    # Generate questions from video metadata
    questions.append(create_multiple_choice(
        f"What is the title of this video?",
        video_info['title'],
        ["Video Title", "Untitled Video", "No Title Available"]
    ))
    
    questions.append(create_multiple_choice(
        f"Who is the creator of this video?",
        video_info['channel_title'],
        ["Unknown Creator", "YouTube User", "Anonymous"]
    ))
    
    # Generate questions from video statistics
    view_count = int(video_info.get('view_count', '0'))
    like_count = int(video_info.get('like_count', '0'))
    
    if view_count > 0:
        questions.append(create_true_false(
            f"This video has more than {view_count//2} views.",
            True
        ))
    
    if like_count > 0:
        questions.append(create_true_false(
            f"The video has received more likes than views.",
            False
        ))
    
    # Generate questions from transcript if available
    if transcript:
        # Combine transcript into a single text
        full_text = " ".join(segment['text'] for segment in transcript)
        
        # Find sentences that could make good fill-in-the-blank questions
        sentences = re.split(r'[.!?]+', full_text)
        valid_sentences = [s.strip() for s in sentences if len(s.split()) > 5 and len(s.split()) < 15]
        
        if valid_sentences:
            # Create a fill-in-the-blank question
            sentence = random.choice(valid_sentences)
            words = sentence.split()
            if len(words) > 5:
                # Remove a random word (not the first or last)
                word_to_remove = random.randint(2, len(words)-2)
                answer = words[word_to_remove]
                words[word_to_remove] = "_____"
                question = " ".join(words)
                questions.append(create_fill_blank(question, answer))
        
        # Create a multiple choice question about content
        if len(valid_sentences) > 3:
            main_sentence = random.choice(valid_sentences)
            other_sentences = random.sample([s for s in valid_sentences if s != main_sentence], 3)
            questions.append(create_multiple_choice(
                "Which of the following statements appears in the video?",
                main_sentence,
                other_sentences
            ))
    
    # Generate questions from description
    if video_info.get('description'):
        desc = video_info['description']
        sentences = re.split(r'[.!?]+', desc)
        valid_desc_sentences = [s.strip() for s in sentences if len(s.split()) > 5]
        
        if valid_desc_sentences:
            sentence = random.choice(valid_desc_sentences)
            questions.append(create_true_false(
                f"The video description mentions: '{sentence}'",
                True
            ))
    
    # Ensure we have exactly 10 questions
    while len(questions) < 10:
        # Add more generic questions if needed
        questions.append(create_multiple_choice(
            "What type of content is this video?",
            "Video Content",
            ["Audio Only", "Image Slideshow", "Text Document"]
        ))
    
    return questions[:10]  # Return exactly 10 questions

def format_quiz(questions: List[Dict[str, Any]]) -> str:
    """Format quiz questions into a readable string."""
    quiz_text = []
    
    for i, q in enumerate(questions, 1):
        quiz_text.append(f"\nQuestion {i} ({q['type'].replace('_', ' ').title()}):")
        quiz_text.append(f"{q['question']}")
        
        if q['type'] == 'multiple_choice':
            for j, option in enumerate(q['options'], 1):
                quiz_text.append(f"{j}. {option}")
        elif q['type'] == 'true_false':
            quiz_text.append("True/False")
        elif q['type'] == 'fill_blank':
            quiz_text.append("Fill in the blank")
        
        quiz_text.append(f"\nAnswer: {q['correct_answer']}")
        quiz_text.append("-" * 50)
    
    return "\n".join(quiz_text)

@mcp.tool()
async def generate_video_quiz(video_id: str) -> str:
    """Generate a quiz based on the video content.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        A formatted quiz with 10 questions of various types
    """
    # Get video details
    video = get_video_details(video_id)
    if not video:
        return "No video found."
    
    # Get transcript
    transcript = get_video_transcript(video_id)
    
    # Generate questions
    questions = generate_quiz_questions(video, transcript)
    
    # Format the quiz
    quiz = format_quiz(questions)
    
    # Add header with video information
    header = f"""
=== Video Quiz ===
Title: {video['title']}
Channel: {video['channel_title']}
URL: {construct_video_url(video_id)}

{quiz}
"""
    return header


@dataclass
class FlashCard:
    """Represents a flash card with front and back content."""
    front: str
    back: str
    timestamp: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None

def extract_key_points(transcript: List[Dict[str, Any]], max_cards: int = 10) -> List[FlashCard]:
    """Extract key points from transcript to create flash cards."""
    cards = []
    
    # Combine transcript into a single text
    full_text = " ".join(segment['text'] for segment in transcript)
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', full_text)
    sentences = [s.strip() for s in sentences if len(s.split()) > 5]
    
    # Create different types of cards
    for i in range(min(max_cards, len(sentences))):
        sentence = sentences[i]
        timestamp = transcript[i]['start'] if i < len(transcript) else None
        
        # Format timestamp as MM:SS
        if timestamp is not None:
            minutes = int(timestamp // 60)
            seconds = int(timestamp % 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
        
        # Create different types of cards
        if i % 3 == 0:  # Fill in the blank
            words = sentence.split()
            if len(words) > 5:
                word_to_remove = random.randint(2, len(words)-2)
                answer = words[word_to_remove]
                words[word_to_remove] = "_____"
                front = " ".join(words)
                back = f"Answer: {answer}\nContext: {sentence}"
                cards.append(FlashCard(
                    front=front,
                    back=back,
                    timestamp=timestamp,
                    category="Fill in the blank",
                    difficulty="Medium"
                ))
        
        elif i % 3 == 1:  # Question-Answer
            words = sentence.split()
            if len(words) > 5:
                front = f"What is the significance of: '{sentence}'?"
                back = f"Explanation: {sentence}"
                cards.append(FlashCard(
                    front=front,
                    back=back,
                    timestamp=timestamp,
                    category="Q&A",
                    difficulty="Easy"
                ))
        
        else:  # Definition
            front = f"Define or explain the concept mentioned at {timestamp}:"
            back = f"Concept: {sentence}"
            cards.append(FlashCard(
                front=front,
                back=back,
                timestamp=timestamp,
                category="Definition",
                difficulty="Hard"
            ))
    
    return cards

def format_flashcards(cards: List[FlashCard]) -> str:
    """Format flash cards into a readable string."""
    output = []
    
    for i, card in enumerate(cards, 1):
        output.append(f"\n=== Card {i} ===")
        output.append(f"Category: {card.category}")
        output.append(f"Difficulty: {card.difficulty}")
        if card.timestamp:
            output.append(f"Timestamp: {card.timestamp}")
        output.append("\nFront:")
        output.append(card.front)
        output.append("\nBack:")
        output.append(card.back)
        output.append("-" * 50)
    
    return "\n".join(output)

@mcp.tool()
async def generate_video_flashcards(
    video_id: str,
    max_cards: int = 10,
    categories: Optional[List[str]] = None,
    difficulty: Optional[str] = None
) -> str:
    """Generate flash cards from a YouTube video's content.
    
    Args:
        video_id: YouTube video ID
        max_cards: Maximum number of cards to generate (default: 10)
        categories: List of card categories to include (default: all)
        difficulty: Filter by difficulty level (Easy/Medium/Hard)
        
    Returns:
        Formatted string containing flash cards
    """
    # Get video details
    video = get_video_details(video_id)
    if not video:
        return "No video found."
    
    # Get transcript
    transcript = get_video_transcript(video_id)
    if not transcript:
        return "No transcript available for this video. Cannot generate flash cards."
    
    # Generate cards
    cards = extract_key_points(transcript, max_cards=max_cards)
    
    # Filter by categories if specified
    if categories:
        cards = [card for card in cards if card.category in categories]
    
    # Filter by difficulty if specified
    if difficulty:
        cards = [card for card in cards if card.difficulty == difficulty]
    
    # Format the output
    header = f"""
=== Video Flash Cards ===
Title: {video['title']}
Channel: {video['channel_title']}
URL: {construct_video_url(video_id)}
Total Cards: {len(cards)}

"""
    
    # Add card statistics
    categories_count = {}
    difficulties_count = {}
    for card in cards:
        categories_count[card.category] = categories_count.get(card.category, 0) + 1
        difficulties_count[card.difficulty] = difficulties_count.get(card.difficulty, 0) + 1
    
    stats = "\n=== Card Statistics ===\n"
    stats += "Categories:\n"
    for category, count in categories_count.items():
        stats += f"- {category}: {count} cards\n"
    stats += "\nDifficulties:\n"
    for diff, count in difficulties_count.items():
        stats += f"- {diff}: {count} cards\n"
    
    # Format the cards
    cards_text = format_flashcards(cards)
    
    return header + stats + cards_text

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
