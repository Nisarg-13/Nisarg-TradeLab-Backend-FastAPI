from fastapi import HTTPException, status


def assert_resource_ownership(resource_user_id: str, current_user_id: str) -> None:
    if resource_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource",
        )
