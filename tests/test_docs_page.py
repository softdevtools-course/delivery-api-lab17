from fastapi.testclient import TestClient

from delivery_lab.main import create_app


def test_docs_contains_progress_panel_and_swagger(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))

    response = client.get("/docs")

    assert response.status_code == 200
    html = response.text
    assert html.index('id="progress-panel"') < html.index('id="swagger-ui"')
    assert 'id="student-token"' in html
    assert 'id="registration-form"' in html
    assert 'id="copy-token"' in html
    assert "swagger-ui-bundle.js" in html
    assert "/static/progress.js" in html


def test_progress_text_does_not_reveal_target_ids_or_endpoint_sequence(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    token = client.post(
        "/auth/register",
        json={"surname": "Тестов", "first_name": "Тест", "group_name": "23-ИС-1"},
    ).json()["access_token"]

    docs = client.get("/docs").text
    tasks = client.get("/progress", headers={"Authorization": f"Bearer {token}"}).json()

    for task in tasks:
        assert task["description"] in docs
        assert "shipment_id" not in task["description"]
        assert "endpoint" not in task["description"].lower()


def test_custom_docs_does_not_store_token_in_browser_storage(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))
    response = client.get("/docs")

    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text


def test_swagger_responses_refresh_progress_and_announce_changes(tmp_path):
    client = TestClient(create_app(tmp_path / "delivery.sqlite3"))

    page = client.get("/docs").text
    script = client.get("/static/progress.js").text

    assert 'id="progress-toast"' in page
    assert 'id="completion-message"' in page
    assert "Задание успешно выполнено! На этом лабораторная работа завершена." in page
    assert "responseInterceptor" in script
    assert 'pathname !== "/progress"' in script
    assert "Прогресс обновлён" in script
    assert "allCompleted" in script
