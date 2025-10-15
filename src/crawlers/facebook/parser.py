"""
Facebook Post Parser - Extract data from GraphQL responses
"""
from typing import Dict, Any, Optional
import time


def safe_get(obj, *paths):
    """
    Safely navigate nested dictionary paths

    Args:
        obj: Dictionary to navigate
        *paths: Path components

    Returns:
        Value at path or None
    """
    for path in paths:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(path)
        elif isinstance(obj, list) and isinstance(path, int):
            try:
                obj = obj[path]
            except IndexError:
                return None
        else:
            return None
    return obj


def parse_count(count_str) -> int:
    """
    Parse Facebook count strings like '2.9K', '1.5M', '298'

    Args:
        count_str: Count string from Facebook

    Returns:
        Integer count
    """
    if isinstance(count_str, int):
        return count_str

    if isinstance(count_str, str):
        count_str = count_str.upper().replace(',', '').strip()

        if 'K' in count_str:
            return int(float(count_str.replace('K', '')) * 1000)
        if 'M' in count_str:
            return int(float(count_str.replace('M', '')) * 1000000)

        try:
            return int(count_str)
        except ValueError:
            return 0

    return 0


def extract_author_info(story: Dict) -> tuple:
    """
    Extract author ID and name from story object

    Returns:
        Tuple of (author_id, author_name)
    """
    author_id = None
    author_name = None

    # Method 1: From actors array (preferred)
    actors = safe_get(story, 'comet_sections', 'content', 'story', 'actors')
    if actors and isinstance(actors, list) and len(actors) > 0:
        actor = actors[0]
        author_id = actor.get('id')
        author_name = actor.get('name')
        if author_id:
            return author_id, author_name

    # Method 2: From owning_profile
    profile = safe_get(
        story, 'comet_sections', 'feedback', 'story',
        'story_ufi_container', 'story', 'feedback_context',
        'feedback_target_with_context', 'owning_profile'
    )
    if profile:
        author_id = profile.get('id')
        author_name = profile.get('name')
        if author_id:
            return author_id, author_name

    # Method 3: From context_layout
    context_actors = safe_get(
        story, 'comet_sections', 'context_layout', 'story',
        'comet_sections', 'actor_photo', 'story', 'actors'
    )
    if context_actors and isinstance(context_actors, list) and len(context_actors) > 0:
        actor = context_actors[0]
        author_id = actor.get('id')
        author_name = actor.get('name')
        if author_id:
            return author_id, author_name

    # Fallback: Get name only
    if not author_name:
        author_name = safe_get(story, 'comet_sections', 'content', 'story', 'actors', 0, 'name') or 'Unknown'

    # Generate fallback ID from name hash
    if not author_id:
        author_id = f'fb_user_{hash(author_name) % 1000000000}'

    return author_id, author_name


def extract_reactions(story: Dict) -> Dict[str, int]:
    """Extract reaction counts from story"""
    reactions = {}

    ufi_feedback = safe_get(
        story, 'comet_sections', 'feedback', 'story',
        'story_ufi_container', 'story', 'feedback_context',
        'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
        'feedback'
    )

    if not ufi_feedback:
        return reactions

    # Total reactions
    total = ufi_feedback.get('i18n_reaction_count')
    if total:
        reactions['total'] = parse_count(total)

    # Reaction breakdown
    top_reactions = safe_get(ufi_feedback, 'top_reactions', 'edges')
    if top_reactions:
        for edge in top_reactions:
            reaction_node = edge.get('node', {})
            name = reaction_node.get('localized_name') or reaction_node.get('reaction_type')
            count = edge.get('reaction_count') or edge.get('i18n_reaction_count')

            if name and count:
                reactions[name] = parse_count(count)

    return reactions


def extract_attachments(story: Dict) -> list:
    """Extract media attachments from story"""
    attachments = []
    story_attachments = story.get('attachments', []) or []

    for att in story_attachments:
        try:
            media = safe_get(att, 'styles', 'attachment', 'media')
            if not media:
                continue

            att_obj = {
                'type': media.get('__typename') if isinstance(media, dict) else None,
                'id': media.get('id') if isinstance(media, dict) else None,
                'url': None,
                'thumbnail': None
            }

            # Get URL
            url = safe_get(att, 'styles', 'attachment', 'url')
            if not url and media:
                url = media.get('url')

            # Get thumbnail
            thumb = safe_get(media, 'thumbnailImage', 'uri')
            if not thumb:
                thumb = safe_get(media, 'preferred_story_attachment_image', 'uri')

            if url or att_obj['id']:
                att_obj['url'] = url
                att_obj['thumbnail'] = thumb
                attachments.append(att_obj)

        except Exception:
            continue

    return attachments


def extract_post_from_node(node: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
    """
    Extract post data from Facebook GraphQL search result node

    Args:
        node: GraphQL search result node
        keyword: Search keyword used

    Returns:
        Parsed post data or None if extraction fails
    """
    # Navigate to story object
    story = safe_get(node, 'rendering_strategy', 'view_model', 'click_model', 'story')

    if not story:
        return None

    # Basic post info
    post = {
        'id': story.get('id'),
        'type': story.get('__typename', 'Story'),
        'keyword': keyword,
        'collected_at': int(time.time()),
        'extraction_method': 'graphql'
    }

    # Extract text content
    text = safe_get(
        story, 'comet_sections', 'content', 'story',
        'comet_sections', 'message', 'story', 'message', 'text'
    )
    if not text:
        text = safe_get(story, 'message', 'text')
    post['text'] = text or ''

    # Extract author info
    author_id, author_name = extract_author_info(story)
    post['author_id'] = author_id
    post['owner'] = author_name

    # Extract timestamp
    publish_time = safe_get(story, 'comet_sections', 'timestamp', 'story', 'creation_time')
    if not publish_time:
        publish_time = safe_get(
            story, 'comet_sections', 'context_layout', 'story',
            'comet_sections', 'metadata', 1, 'story', 'creation_time'
        )
    post['publish_time'] = publish_time or 0

    # Extract engagement metrics
    comment_count = safe_get(
        story, 'comet_sections', 'feedback', 'story',
        'story_ufi_container', 'story', 'feedback_context',
        'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
        'feedback', 'comments_count_summary_renderer', 'feedback',
        'comment_rendering_instance', 'comments', 'total_count'
    )
    post['comment_count'] = int(comment_count) if comment_count else 0

    share_count = safe_get(
        story, 'comet_sections', 'feedback', 'story',
        'story_ufi_container', 'story', 'feedback_context',
        'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
        'feedback', 'share_count', 'count'
    )
    post['share_count'] = int(share_count) if share_count else 0

    view_count = safe_get(story, 'attachments', 0, 'styles', 'attachment', 'media', 'video_view_count')
    post['view_count'] = int(view_count) if view_count else 0

    # Extract reactions
    post['reactions'] = extract_reactions(story)

    # Extract attachments
    post['attachments'] = extract_attachments(story)

    return post