import pytest

from django_app.identity.models import User
from infrastructure.identity.django_unit_of_work import DjangoIdentityUnitOfWork


@pytest.mark.django_db
def test_django_identity_unit_of_work_rolls_back_when_not_committed():
    with pytest.raises(RuntimeError, match="stop before commit"):
        with DjangoIdentityUnitOfWork():
            User.objects.create_user(
                email="rollback-uow@example.com",
                password="StrongPass1!",
                first_name="Roll",
                last_name="Back",
                role="planner",
            )
            raise RuntimeError("stop before commit")

    assert not User.objects.filter(email="rollback-uow@example.com").exists()


@pytest.mark.django_db
def test_django_identity_unit_of_work_commits_when_explicitly_committed():
    with DjangoIdentityUnitOfWork() as unit_of_work:
        User.objects.create_user(
            email="commit-uow@example.com",
            password="StrongPass1!",
            first_name="Commit",
            last_name="Uow",
            role="planner",
        )
        unit_of_work.commit()

    assert User.objects.filter(email="commit-uow@example.com").exists()
