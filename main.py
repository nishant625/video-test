
import sys
from dotenv import load_dotenv

from database import init_db, create_run, update_run, add_event
from services.logger import log
from services.gemini import generate_content
from services.kie import create_video, wait_for_video
from services.zernio import get_youtube_accounts, create_post

load_dotenv()
init_db()


def confirm(message):
    answer = input(f"\n{message} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def event(run_id, stage, level, message):
    add_event(run_id, stage, level, message)

    if level == "ERROR":
        log.error(message)
    elif level == "WARNING":
        log.warning(message)
    else:
        log.info(message)


def main():
    print()
    print("╔════════════════════════════════════════════╗")
    print("║          AI VIRAL CONTENT ENGINE           ║")
    print("╚════════════════════════════════════════════╝")
    print()

    idea = input("Enter your video idea/fact: ").strip()

    if not idea:
        print("❌ No idea provided.")
        sys.exit(1)

    run_id = create_run(idea)

    event(run_id, "SYSTEM", "INFO", f"Run #{run_id} started")
    event(run_id, "SYSTEM", "INFO", f"Input idea: {idea}")

    try:

        # ─────────────────────────────────────
        # CONTENT GENERATION
        # ─────────────────────────────────────

        update_run(run_id, status="CONTENT_GENERATING")

        event(
            run_id,
            "GEMINI",
            "INFO",
            "Generating video prompt and YouTube title..."
        )

        video_prompt, youtube_title = generate_content(idea)

        update_run(
            run_id,
            video_prompt=video_prompt,
            youtube_title=youtube_title,
            status="CONTENT_READY",
        )

        event(
            run_id,
            "GEMINI",
            "INFO",
            "Content generation complete."
        )

        print()
        print("════════════════ VIDEO PROMPT ════════════════")
        print(video_prompt)

        print()
        print("════════════════ YOUTUBE TITLE ══════════════")
        print(youtube_title)

        # ─────────────────────────────────────
        # CONFIRM KIE
        # ─────────────────────────────────────

        if not confirm("Proceed to Kie video generation?"):
            update_run(run_id, status="CONTENT_ONLY")
            event(
                run_id,
                "SYSTEM",
                "INFO",
                "User stopped after content generation."
            )
            return

        # ─────────────────────────────────────
        # KIE
        # ─────────────────────────────────────

        update_run(run_id, status="VIDEO_GENERATING")

        event(
            run_id,
            "KIE",
            "INFO",
            "Creating Kie video task..."
        )

        task_id = create_video(video_prompt)

        update_run(
            run_id,
            kie_task_id=task_id,
            kie_state="created",
        )

        video_url = wait_for_video(task_id)

        update_run(
            run_id,
            kie_state="success",
            video_url=video_url,
            status="VIDEO_READY",
        )

        event(
            run_id,
            "KIE",
            "INFO",
            "Video generation SUCCESS."
        )

        print()
        print("════════════════ VIDEO URL ═════════════════")
        print(video_url)

        # ─────────────────────────────────────
        # CONFIRM ZERNIO
        # ─────────────────────────────────────

        if not confirm("Proceed to Zernio publishing setup?"):
            event(
                run_id,
                "SYSTEM",
                "INFO",
                "User stopped after video generation."
            )
            return

        # ─────────────────────────────────────
        # FETCH ZERNIO ACCOUNTS
        # ─────────────────────────────────────

        update_run(run_id, status="ZERNIO_SETUP")

        event(
            run_id,
            "ZERNIO",
            "INFO",
            "Fetching connected accounts..."
        )

        accounts = get_youtube_accounts()

        if not accounts:
            raise RuntimeError(
                "No active YouTube accounts found in Zernio."
            )

        print()
        print("════════════ ZERNIO YOUTUBE ACCOUNTS ════════════")

        for index, account in enumerate(accounts, start=1):

            profile = account.get(
                "metadata",
                {}
            ).get(
                "profileData",
                {}
            )

            name = (
                profile.get("displayName")
                or account.get("displayName")
                or "Unknown"
            )

            username = (
                profile.get("username")
                or account.get("username")
                or "unknown"
            )

            print(
                f"{index}. {name} (@{username})"
            )

        print()

        try:
            selection = int(
                input("Select YouTube account: ")
            ) - 1
        except ValueError:
            raise RuntimeError("Invalid account selection.")

        if selection < 0 or selection >= len(accounts):
            raise RuntimeError("Invalid account selection.")

        account = accounts[selection]

        account_id = account["_id"]

        update_run(
            run_id,
            zernio_account_id=account_id,
            zernio_platform="youtube",
        )

        event(
            run_id,
            "ZERNIO",
            "INFO",
            f"Selected YouTube account: {account_id}"
        )

        # ─────────────────────────────────────
        # POST PREVIEW
        # ─────────────────────────────────────

        print()
        print("════════════════ POST PREVIEW ════════════════")
        print()
        print(f"Account : @{account.get('username')}")
        print(f"Title   : {youtube_title}")
        print(f"Video   : {video_url}")
        print()
        print("══════════════════════════════════════════════")

        # ─────────────────────────────────────
        # FINAL CONFIRMATION
        # ─────────────────────────────────────

        if not confirm(
            "Publish this video to YouTube through Zernio?"
        ):
            update_run(
                run_id,
                status="VIDEO_READY"
            )

            event(
                run_id,
                "ZERNIO",
                "INFO",
                "User cancelled publishing."
            )

            return

        # ─────────────────────────────────────
        # CREATE POST
        # ─────────────────────────────────────

        update_run(
            run_id,
            status="PUBLISHING"
        )

        event(
            run_id,
            "ZERNIO",
            "INFO",
            "Creating YouTube post..."
        )

        result = create_post(
            content=youtube_title,
            video_url=video_url,
            account_id=account_id,
        )

        post_id = (
            result.get("post", {}).get("_id")
            or result.get("_id")
        )

        update_run(
            run_id,
            zernio_post_id=post_id,
            status="PUBLISHED",
        )

        event(
            run_id,
            "ZERNIO",
            "INFO",
            f"Post created successfully. ID: {post_id}"
        )

        print()
        print("════════════════════════════════════════════")
        print("✅ RUN COMPLETE — VIDEO PUBLISHED")
        print(f"Run ID: {run_id}")
        print(f"Post ID: {post_id}")
        print("════════════════════════════════════════════")
        print()

    except Exception as error:

        update_run(
            run_id,
            status="FAILED",
            error_message=str(error),
        )

        event(
            run_id,
            "SYSTEM",
            "ERROR",
            f"Run #{run_id} FAILED: {error}"
        )

        raise


if __name__ == "__main__":
    main()

