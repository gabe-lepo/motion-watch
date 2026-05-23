use crate::{
    config::AppState,
    models::types::{Device, DeviceRegisterParams, DeviceRegisterResponse},
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
                "POST /devices: Recevied request from {:?} at {:?}",
                params.name, params.location,
            );

            sqlx::query_as!(
                Device,
                "INSERT INTO devices (name, location)
                VALUES ($1, $2)
                RETURNING *",
                params.name,
                params.location,
            );

            let response = DeviceRegisterResponse {
                name: params.name,
                location: params.location,
            };
            (StatusCode::CREATED, Json(response)).into_response()
        }
        Err(e) => {
            println!("POST /devices: Bad request body:");
            println!("\t{}", e.body_text());
            (StatusCode::UNPROCESSABLE_ENTITY, e.body_text()).into_response()
        }
    }
}

/// Get all devices via 'GET /devices'
pub async fn get_all() {
    todo!()
}

/// Get a single device by id via 'GET /devices/{id}'
pub async fn get_by_id(Path(id): Path<uuid::Uuid>) {
    todo!()
}

/// Update a single device by id via 'PATCH /devices/{id}'
pub async fn update_by_id(Path(id): Path<uuid::Uuid>) {
    todo!()
}
