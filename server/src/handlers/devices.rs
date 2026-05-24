use crate::{
    config::AppState,
    models::types::{Device, DeviceRegisterParams},
    utils::unix_ms,
};
use axum::{
    extract::{Json, Path, State, rejection::JsonRejection},
    http::StatusCode,
    response::IntoResponse,
};

/// Register a new device via 'POST /devices'
pub async fn register(
    State(app_state): State<AppState>,
    payload: Result<Json<DeviceRegisterParams>, JsonRejection>,
) -> impl IntoResponse {
    match payload {
        Ok(Json(params)) => {
            println!(
                "POST /devices: Recevied request from device {:?}",
                params.hw_identifier,
            );

            match sqlx::query_as!(
                Device,
                "INSERT INTO devices (hw_identifier, name, location)
                    VALUES ($1, $2, $3)
                    RETURNING *",
                params.hw_identifier,
                params.name,
                params.location,
            )
            .fetch_one(&app_state.db_pool)
            .await
            {
                Ok(device) => (StatusCode::CREATED, Json(device)).into_response(),
                Err(e) => {
                    eprintln!("Error registering device: {e}");
                    let status = match e {
                        sqlx::Error::Database(db_err) => {
                            // FIXME: Need to handle sqlx -> status codes elsewhere
                            // Theres too much match nesting going on directly in handlers
                            match db_err.code().as_deref() {
                                _ => 
                            }
                        },
                        _ => StatusCode::INTERNAL_SERVER_ERROR,
                    }
                    (
                        status,
                        Json(serde_json::json!({"error": e.to_string()})),
                    )
                        .into_response()
                }
            }
        }
        Err(e) => {
            println!("POST /devices: Bad request body:");
            println!("\t{}", e.body_text());
            (StatusCode::UNPROCESSABLE_ENTITY, e.body_text()).into_response()
        }
    }
}

/// Update a single device by id via 'PATCH /devices/{id}'
pub async fn update_by_id(
    State(app_state): State<AppState>,
    Path(id): Path<uuid::Uuid>,
) -> impl IntoResponse {
    println!("PATCH /devices/{id}");

    match sqlx::query_as!(
        Device,
        "UPDATE devices SET last_seen = $1
        WHERE id = $2
        RETURNING *",
        unix_ms() as i64,
        id,
    )
    .fetch_one(&app_state.db_pool)
    .await
    {
        Ok(device) => (StatusCode::OK, Json(device)).into_response(),
        Err(e) => {
            eprintln!("Error updating device {}: {}", id, e);
            let status = match e {
                sqlx::Error::RowNotFound => StatusCode::NOT_FOUND,
                _ => StatusCode::INTERNAL_SERVER_ERROR,
            };

            (status, Json(serde_json::json!({"error": e.to_string()}))).into_response()
        }
    }
}

/// Get a single device by id via 'GET /devices/{id}'
pub async fn get_by_id(
    State(app_state): State<AppState>,
    Path(id): Path<uuid::Uuid>,
) -> impl IntoResponse {
    println!("GET /devices/{id}");

    match sqlx::query_as!(Device, "SELECT * FROM devices WHERE id = $1", id)
        .fetch_one(&app_state.db_pool)
        .await
    {
        Ok(device) => (StatusCode::OK, Json(device)).into_response(),
        Err(e) => {
            eprintln!("Error getting device {}: {}", id, e);
            let status = match e {
                sqlx::Error::RowNotFound => StatusCode::NOT_FOUND,
                _ => StatusCode::INTERNAL_SERVER_ERROR,
            };

            (status, Json(serde_json::json!({"error": e.to_string()}))).into_response()
        }
    }
}

/// Get all devices via 'GET /devices'
pub async fn get_all(State(app_state): State<AppState>) -> impl IntoResponse {
    println!("GET /devices/: Received request");

    match sqlx::query_as!(Device, "SELECT * from devices")
        .fetch_all(&app_state.db_pool)
        .await
    {
        Ok(devices) => (StatusCode::OK, Json(devices)).into_response(),
        Err(e) => {
            eprintln!("Error getting all devices: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": e.to_string()})),
            )
                .into_response()
        }
    }
}
