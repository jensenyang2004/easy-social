from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import joinedload

from .extensions import db
from .media import save_media
from .models import Comment, Poll, PollOption, PollVote, Post, User, followers

bp = Blueprint("social", __name__)


def _post_query():
    return Post.query.options(
        joinedload(Post.author),
        joinedload(Post.repost_of).joinedload(Post.author),
        joinedload(Post.poll).joinedload(Poll.options),
    )


def _comment_counts_for_posts(posts: list[Post]) -> dict[int, int]:
    post_ids = {post.display_post.id for post in posts}
    if not post_ids:
        return {}

    counts = dict.fromkeys(post_ids, 0)
    rows = (
        db.session.query(Comment.post_id, func.count(Comment.id))
        .filter(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
        .all()
    )
    counts.update({post_id: count for post_id, count in rows})
    return counts


def _followed_user_ids(users: list[User]) -> set[int]:
    user_ids = [user.id for user in users]
    if not user_ids:
        return set()

    return {
        followed_id
        for (followed_id,) in db.session.query(followers.c.followed_id)
        .filter(
            followers.c.follower_id == current_user.id,
            followers.c.followed_id.in_(user_ids),
        )
        .all()
    }


@bp.route("/")
@login_required
def feed():
    followed_ids = db.session.query(followers.c.followed_id).filter(
        followers.c.follower_id == current_user.id
    )
    posts = (
        _post_query()
        .filter(or_(Post.author_id == current_user.id, Post.author_id.in_(followed_ids)))
        .order_by(desc(Post.created_at))
        .limit(100)
        .all()
    )
    return render_template(
        "social/feed.html",
        posts=posts,
        comment_counts=_comment_counts_for_posts(posts),
    )


@bp.route("/explore")
@login_required
def explore():
    posts = _post_query().order_by(desc(Post.created_at)).limit(100).all()
    users = User.query.filter(User.id != current_user.id).order_by(User.username).limit(50).all()
    return render_template(
        "social/explore.html",
        posts=posts,
        users=users,
        comment_counts=_comment_counts_for_posts(posts),
        followed_user_ids=_followed_user_ids(users),
    )


@bp.post("/api/posts")
@login_required
def create_post_api():
    data = request.get_json()
    if not data:
        return {"error": "Invalid JSON"}, 400

    body = data.get("content", "").strip()
    poll_data = data.get("poll")

    if not body:
        return {"error": "Content is required"}, 400

    post = Post(body=body, author=current_user)
    db.session.add(post)
    db.session.flush()

    poll_result = None
    if poll_data:
        options = poll_data.get("options", [])
        if len(options) < 2 or len(options) > 4:
            return {"error": "Poll must have between 2 and 4 options"}, 400

        poll = Poll(post_id=post.id)
        db.session.add(poll)
        db.session.flush()

        for i, opt_text in enumerate(options):
            if not opt_text.strip():
                return {"error": "All options must have text"}, 400
            if len(opt_text) > 100:
                return {"error": "Option text is too long"}, 400
            db.session.add(PollOption(poll_id=poll.id, text=opt_text, order=i))

        db.session.flush()
        poll_result = {
            "id": poll.id,
            "options": [{"id": o.id, "text": o.text} for o in poll.options],
        }

    db.session.commit()

    return {
        "id": post.id,
        "body": post.body,
        "author_id": post.author_id,
        "created_at": post.created_at.isoformat(),
        "poll": poll_result,
    }, 201


@bp.post("/api/polls/<poll_id>/vote")
@login_required
def vote_poll(poll_id: str):
    data = request.get_json()
    if not data:
        return {"error": "Invalid JSON"}, 400

    option_id = data.get("option_id")
    if not option_id:
        return {"error": "option_id is required"}, 400

    poll = Poll.query.get_or_404(poll_id)
    option = PollOption.query.get_or_404(option_id)

    if option.poll_id != poll.id:
        return {"error": "Option does not belong to this poll"}, 400

    if poll.get_user_vote(current_user.id):
        return {"error": "You have already voted on this poll"}, 409

    vote = PollVote(poll_id=poll.id, option_id=option.id, user_id=current_user.id)
    db.session.add(vote)
    db.session.commit()

    return {"success": True, "results": poll.get_results()}, 200


@bp.get("/api/polls/<poll_id>/results")
@login_required
def get_poll_results(poll_id: str):
    poll = Poll.query.get_or_404(poll_id)
    user_vote = poll.get_user_vote(current_user.id)

    return {
        "results": poll.get_results(),
        "user_voted_option_id": user_vote.option_id if user_vote else None,
    }, 200


@bp.post("/posts")
@login_required
def create_post():
    body = request.form.get("body", "").strip()

    try:
        media_filename, media_type = save_media(request.files.get("media"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("social.feed"))

    if not body and not media_filename:
        flash("Add text, an image, or a video before posting.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    post = Post(
        body=body,
        media_filename=media_filename,
        media_type=media_type,
        author=current_user,
    )
    db.session.add(post)
    db.session.flush()

    poll_options = [o.strip() for o in request.form.getlist("poll_option") if o.strip()]
    if poll_options:
        if len(poll_options) < 2 or len(poll_options) > 4:
            flash("Poll must have between 2 and 4 options.", "error")
            db.session.rollback()
            return redirect(request.referrer or url_for("social.feed"))

        poll = Poll(post_id=post.id)
        db.session.add(poll)
        db.session.flush()

        for i, opt_text in enumerate(poll_options):
            if len(opt_text) > 100:
                flash("Option text is too long.", "error")
                db.session.rollback()
                return redirect(request.referrer or url_for("social.feed"))
            db.session.add(PollOption(poll_id=poll.id, text=opt_text, order=i))

    db.session.commit()
    return redirect(url_for("social.feed"))


@bp.get("/posts/<int:post_id>")
@login_required
def post_detail(post_id: int):
    post = _post_query().filter(Post.id == post_id).first_or_404()
    comments = post.comments.order_by(Comment.created_at.asc()).all()
    return render_template(
        "social/post_detail.html",
        post=post,
        comments=comments,
        comment_counts={post.display_post.id: len(comments)},
    )


@bp.post("/posts/<int:post_id>/comments")
@login_required
def add_comment(post_id: int):
    post = db.get_or_404(Post, post_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
    else:
        db.session.add(Comment(body=body, author=current_user, post=post))
        db.session.commit()
    return redirect(url_for("social.post_detail", post_id=post.id))


@bp.post("/posts/<int:post_id>/repost")
@login_required
def repost(post_id: int):
    original = db.get_or_404(Post, post_id).display_post
    if original.author_id == current_user.id:
        flash("You cannot repost your own post.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    existing = Post.query.filter_by(author_id=current_user.id, repost_of_id=original.id).first()
    if existing:
        flash("You already reposted this.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    db.session.add(Post(author=current_user, repost_of=original))
    db.session.commit()
    return redirect(request.referrer or url_for("social.feed"))


@bp.route("/users/<username>")
@login_required
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    posts = (
        _post_query()
        .filter(Post.author_id == user.id)
        .order_by(desc(Post.created_at))
        .all()
    )
    return render_template(
        "social/profile.html",
        profile_user=user,
        posts=posts,
        comment_counts=_comment_counts_for_posts(posts),
    )


@bp.post("/users/<username>/follow")
@login_required
def follow(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.follow(user)
    db.session.commit()
    return redirect(request.referrer or url_for("social.profile", username=user.username))


@bp.post("/users/<username>/unfollow")
@login_required
def unfollow(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.unfollow(user)
    db.session.commit()
    return redirect(request.referrer or url_for("social.profile", username=user.username))
