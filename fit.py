from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime

SCOPES = ["https://www.googleapis.com/auth/fitness.activity.read"]

def auth():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    service = build("fitness", "v1", credentials=creds)
    return service

def today_nanos():
    today = datetime.date.today()
    start = datetime.datetime.combine(today, datetime.time.min)
    end = datetime.datetime.combine(today, datetime.time.max)
    return int(start.timestamp() * 1e9), int(end.timestamp() * 1e9)

def get_steps(service):
    start_ns, end_ns = today_nanos()
    datasource = "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
    dataset = f"{start_ns}-{end_ns}"
    response = service.users().dataSources().datasets().get(
        userId="me", dataSourceId=datasource, datasetId=dataset).execute()
    total = 0
    for point in response.get("point", []):
        total += point["value"][0]["intVal"]
    return total

def get_active_minutes(service):
    start_ns, end_ns = today_nanos()
    datasource = "derived:com.google.active_minutes:com.google.android.gms:merge_active_minutes"
    dataset = f"{start_ns}-{end_ns}"
    response = service.users().dataSources().datasets().get(
        userId="me", dataSourceId=datasource, datasetId=dataset).execute()
    total = 0
    for point in response.get("point", []):
        total += point["value"][0]["intVal"]
    return total

def get_calories(service):
    start_ns, end_ns = today_nanos()
    datasource = "derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended"
    dataset = f"{start_ns}-{end_ns}"
    response = service.users().dataSources().datasets().get(
        userId="me", dataSourceId=datasource, datasetId=dataset).execute()
    total = 0.0
    for point in response.get("point", []):
        total += point["value"][0]["fpVal"]
    return total

def get_heart_points(service):
    start_ns, end_ns = today_nanos()
    datasource = "derived:com.google.heart_minutes:com.google.android.gms:merge_heart_minutes"
    dataset = f"{start_ns}-{end_ns}"
    response = service.users().dataSources().datasets().get(
        userId="me", dataSourceId=datasource, datasetId=dataset).execute()
    total = 0.0
    for point in response.get("point", []):
        total += point["value"][0]["fpVal"]
    return total

def collect_data():
    service = auth()
    return {
        "steps": get_steps(service),
        "active_minutes": get_active_minutes(service),
        "calories_burned": get_calories(service),
        "heart_points": get_heart_points(service),
    }

if __name__ == "__main__":
    sensor_data = collect_data()

    print("Steps:", sensor_data["steps"])
    print("Active Minutes:", sensor_data["active_minutes"])
    print("Calories Burned (kcal):", round(sensor_data["calories_burned"], 1))
    print("Heart Points:", round(sensor_data["heart_points"], 1))
