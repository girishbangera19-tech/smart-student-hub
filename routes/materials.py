"""Study materials: secure upload, list/filter, download, delete.

Safety rules used here:
  * files are stored OUTSIDE /static, under a random name (the user's filename is never used on disk)
  * extension must be in ALLOWED_EXTENSIONS, and PDFs must really start with '%PDF'
  * size is limited by MAX_CONTENT_LENGTH (10 MB)
  * downloads check that the file belongs to the logged-in student
"""
import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import db
from helpers import clean, form_values, owned_or_404
from models import StudyMaterial

materials_bp = Blueprint("materials", __name__, url_prefix="/materials")

RESOURCE_TYPES = ["Notes", "Module PDF", "Question Paper", "Question Bank", "Lab Manual",
                  "Presentation", "Reference Document"]
FIELDS = ("title", "description", "subject_name", "subject_code", "semester", "module_number",
          "resource_type", "scheme")


def check_upload(file):
    """Return (extension, error). Validates name, extension and file signature."""
    if file is None or not file.filename:
        return None, "Please choose a file to upload."
    name = secure_filename(file.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        allowed = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
        return None, f"File type not allowed. Allowed types: {allowed}."
    head = file.stream.read(8)
    file.stream.seek(0)
    if ext == "pdf" and not head.startswith(b"%PDF"):
        return None, "That file is not a valid PDF."
    if ext in ("docx", "pptx") and not head.startswith(b"PK"):
        return None, f"That file is not a valid .{ext} document."
    if ext in ("doc", "ppt") and not head.startswith(b"\xd0\xcf\x11\xe0"):
        return None, f"That file is not a valid .{ext} document."
    return ext, None


def validate(form):
    errors = []
    if not form["title"]:
        errors.append("Title is required.")
    if not form["subject_name"]:
        errors.append("Subject is required.")
    if form["resource_type"] not in RESOURCE_TYPES:
        errors.append("Please choose a resource type.")
    semester = module = None
    if form["semester"]:
        if form["semester"].isdigit() and 1 <= int(form["semester"]) <= 8:
            semester = int(form["semester"])
        else:
            errors.append("Semester must be between 1 and 8.")
    if form["module_number"]:
        if form["module_number"].isdigit() and 1 <= int(form["module_number"]) <= 10:
            module = int(form["module_number"])
        else:
            errors.append("Module number must be between 1 and 10.")
    data = {"title": form["title"][:150], "description": form["description"] or None,
            "subject_name": form["subject_name"][:120], "subject_code": form["subject_code"][:20] or None,
            "semester": semester, "module_number": module, "resource_type": form["resource_type"],
            "scheme": form["scheme"][:20] or None}
    return data, errors


@materials_bp.route("/")
@login_required
def index():
    q = clean(request.args.get("q"))
    subject = clean(request.args.get("subject"))
    rtype = clean(request.args.get("type"))
    semester = clean(request.args.get("semester"))
    module = clean(request.args.get("module"))
    sort = request.args.get("sort", "newest")

    base = StudyMaterial.query.filter_by(user_id=current_user.id)
    query = base
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(StudyMaterial.title.ilike(like), StudyMaterial.subject_name.ilike(like),
                                    StudyMaterial.description.ilike(like), StudyMaterial.subject_code.ilike(like)))
    if subject:
        query = query.filter(StudyMaterial.subject_name == subject)
    if rtype in RESOURCE_TYPES:
        query = query.filter(StudyMaterial.resource_type == rtype)
    if semester.isdigit():
        query = query.filter(StudyMaterial.semester == int(semester))
    if module.isdigit():
        query = query.filter(StudyMaterial.module_number == int(module))
    query = query.order_by(StudyMaterial.uploaded_at if sort == "oldest" else StudyMaterial.uploaded_at.desc())

    subjects = [s for (s,) in db.session.query(StudyMaterial.subject_name)
                .filter_by(user_id=current_user.id).distinct().order_by(StudyMaterial.subject_name)]
    return render_template("materials/index.html", materials=query.all(), subjects=subjects, types=RESOURCE_TYPES,
                           q=q, subject=subject, rtype=rtype, semester=semester, module=module, sort=sort,
                           total=base.count())


@materials_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = {"semester": str(current_user.semester), "scheme": current_user.scheme or ""}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        file = request.files.get("file")
        ext, file_error = check_upload(file)
        if file_error:
            errors.append(file_error)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("materials/upload.html", form=form, types=RESOURCE_TYPES), 400

        stored = f"{uuid.uuid4().hex}.{ext}"  # random, safe name on disk
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
        file.save(path)
        db.session.add(StudyMaterial(user_id=current_user.id, original_filename=secure_filename(file.filename),
                                     stored_filename=stored, file_size=os.path.getsize(path), **data))
        db.session.commit()
        flash("Study material uploaded.", "success")
        return redirect(url_for("materials.index"))
    return render_template("materials/upload.html", form=form, types=RESOURCE_TYPES)


@materials_bp.route("/<int:material_id>/download")
@login_required
def download(material_id):
    material = owned_or_404(StudyMaterial, material_id)
    # ?inline=1 lets the browser preview PDFs instead of downloading them.
    inline = request.args.get("inline") == "1" and material.stored_filename.endswith(".pdf")
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], material.stored_filename,
                               as_attachment=not inline, download_name=material.original_filename)


@materials_bp.route("/<int:material_id>/delete", methods=["POST"])
@login_required
def delete(material_id):
    material = owned_or_404(StudyMaterial, material_id)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], material.stored_filename)
    db.session.delete(material)
    db.session.commit()
    try:
        os.remove(path)
    except OSError:
        pass  # file already gone; the database row is removed either way
    flash("Material deleted.", "success")
    return redirect(url_for("materials.index"))
