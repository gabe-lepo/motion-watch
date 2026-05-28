use serde::Deserialize;
use sqlx::{Pool, Postgres};
use std::env;

#[derive(Clone)]
pub struct AppState {
    pub config: AppConfig,
    pub db_pool: Pool<Postgres>,
}

#[derive(Deserialize, Debug, Clone)]
pub struct AppConfig {
    pub database_url: String,
    pub port: u16,
}

impl AppConfig {
    /// Load env vars then deserialize into AppConfig
    pub fn new() -> Self {
        dotenvy::dotenv().ok();
        let port = env::var("PORT")
            .expect("Failed loading port from env var")
            .parse::<u16>()
            .expect("Failed parsing port env var");
        let database_url = env::var("DATABASE_URL").expect("Failed loading database_url env var");
        println!("DEBUG: {database_url}");

        Self { database_url, port }
    }
}
