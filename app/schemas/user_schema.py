def serialize_user(user):
    """Serialize a User model instance."""
    if not user:
        return {}
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "preferred_language": user.preferred_language,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_profile(profile):
    """Serialize a Profile model instance."""
    if not profile:
        return {}
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "name": profile.name,
        "relationship": profile.relationship,
        "age": profile.age,
        "gender": profile.gender,
        "notes": profile.notes,
        "is_default": profile.is_default,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }
