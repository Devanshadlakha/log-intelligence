package com.logintel.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Represents a single log entry flowing through the system.
 * This same object is:
 *   - Produced to Kafka as JSON
 *   - Consumed from Kafka and saved to Elasticsearch
 *   - Returned by the Search API to the frontend
 */
@Data               // generates getters, setters, toString, equals, hashCode
@Builder            // allows LogEntry.builder().service("payment").build()
@NoArgsConstructor  // required for JSON deserialization
@AllArgsConstructor // required for @Builder
public class LogEntry {

    // Unique ID for this log — used as Elasticsearch document ID
    private String id;

    // Which service generated this log (e.g. "payment", "auth", "inventory")
    private String service;

    // Log level: INFO, WARN, ERROR
    private String level;

    // The actual log message
    private String message;

    // When this log was generated
    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private Instant timestamp;

    // Optional: which host/server generated this (useful for filtering)
    private String host;

    // Optional: trace ID for correlating related logs
    private String traceId;
}