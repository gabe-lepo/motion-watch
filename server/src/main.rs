#![allow(dead_code, unused)]

mod config;
mod db;
mod handlers;
mod models;

use axum::{
    Router,
    routing::{get, patch, post},
};
use handlers::devices;
use sqlx::postgres::PgPoolOptions;

use crate::config::{AppConfig, AppState};

#[tokio::main]
async fn main() -> Result<(), sqlx::Error> {
    // App setup
    let mut app_state = AppState {
        config: AppConfig::new(),
        db_pool: None,
    };

    // Setup postgres pool
    let pg_pool = PgPoolOptions::new()
        .min_connections(1)
        .max_connections(5)
        .acquire_timeout(std::time::Duration::new(5, 0))
        .connect(&app_state.config.database_url)
        .await?;

    println!("Connected to Postgres DB");

    app_state.db_pool = Some(pg_pool);

    // Setup axum routing
    let app = Router::new()
        // Device table routes
        .route("/devices", post(devices::register))
        .route("/devices", get(devices::get_all))
        .route("/devices/{id}", get(devices::get_by_id))
        .route("/devices/{id}", patch(devices::update_by_id))
        .with_state(app_state);

    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", &app_state.config.port))
        .await
        .unwrap();

    println!("-------------------------");
    println!("Listening on port {}...", app_state.config.port);
    println!("-------------------------");
    println!("\tPOST\t/device/create");
    println!("\tPOST\t/device/update");
    println!("\tGET\t\t/device/read");
    println!("\tPOST\t/event/create");
    println!("\tPOST\t/event/update");
    println!("\tGET\t\t/event/read");
    println!("-------------------------");

    axum::serve(listener, app).await.unwrap();

    Ok(())
}
