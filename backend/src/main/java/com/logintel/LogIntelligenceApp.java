package com.logintel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point for the Log Intelligence backend.
 *
 * @SpringBootApplication = auto-configures everything Spring needs
 */
@SpringBootApplication
public class LogIntelligenceApp {

    public static void main(String[] args) {
        SpringApplication.run(LogIntelligenceApp.class, args);
    }
}