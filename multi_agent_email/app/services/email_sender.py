from app.models import FinalEmail


def send_email(email: FinalEmail) -> None:
    """
    Pour l'instant, on simule l'envoi en affichant l'email dans le terminal.
    """
    print("=== ENVOI D'EMAIL (simulé) ===")
    print(f"À      : {email.recipient}")
    print(f"Sujet  : {email.subject}")
    print()
    print(email.body)
    print("================================")
