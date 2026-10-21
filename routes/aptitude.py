"""Aptitude practice: quizzes by category, scoring, explanations and saved attempts."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from aptitude_data import CATEGORIES, QUESTIONS
from extensions import db
from models import AptitudeAttempt, AptitudeQuestion

aptitude_bp = Blueprint("aptitude", __name__, url_prefix="/aptitude")


def ensure_questions():
    """Load the sample questions the first time they are needed (safe to call repeatedly)."""
    if AptitudeQuestion.query.count() == 0:
        for cat, q, a, b, c, d, correct, why in QUESTIONS:
            db.session.add(AptitudeQuestion(category=cat, question=q, option_a=a, option_b=b,
                                            option_c=c, option_d=d, correct_option=correct, explanation=why))
        db.session.commit()


@aptitude_bp.route("/")
@login_required
def index():
    ensure_questions()
    counts = {c: AptitudeQuestion.query.filter_by(category=c).count() for c in CATEGORIES}
    attempts = (AptitudeAttempt.query.filter_by(user_id=current_user.id)
                .order_by(AptitudeAttempt.taken_at.desc()).limit(10).all())
    return render_template("aptitude/index.html", categories=CATEGORIES, counts=counts, attempts=attempts)


@aptitude_bp.route("/<category>", methods=["GET", "POST"])
@login_required
def quiz(category):
    if category not in CATEGORIES:
        abort(404)
    ensure_questions()
    questions = AptitudeQuestion.query.filter_by(category=category).order_by(AptitudeQuestion.id).all()

    if request.method == "GET":
        return render_template("aptitude/quiz.html", category=category, questions=questions, result=None)

    # Score the submission on the server (the correct answers are never trusted from the browser).
    answers, score = {}, 0
    for q in questions:
        choice = request.form.get(f"q_{q.id}", "")
        answers[q.id] = choice if choice in ("a", "b", "c", "d") else ""
        if answers[q.id] == q.correct_option:
            score += 1
    if not any(answers.values()):
        flash("Please answer at least one question before submitting.", "warning")
        return render_template("aptitude/quiz.html", category=category, questions=questions, result=None), 400

    db.session.add(AptitudeAttempt(user_id=current_user.id, category=category, score=score, total=len(questions)))
    db.session.commit()
    flash(f"You scored {score} out of {len(questions)}.", "success")
    return render_template("aptitude/quiz.html", category=category, questions=questions,
                           result={"score": score, "total": len(questions), "answers": answers})
