package com.logintel.config;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Elasticsearch configuration — creates the ElasticsearchClient bean
 * that we inject into our search service to query ES.
 */
@Configuration
public class ElasticsearchConfig {

    @Value("${elasticsearch.host}")
    private String host;

    @Value("${elasticsearch.port}")
    private int port;

    /**
     * Creates a configured ObjectMapper that handles:
     * - Java 8 date/time types (Instant, LocalDateTime)
     * - Proper JSON serialization of timestamps
     */
    @Bean
    public ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        // Register module to handle Instant, LocalDateTime etc.
        mapper.registerModule(new JavaTimeModule());
        // Write dates as ISO strings not timestamps
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        return mapper;
    }

    /**
     * Creates the low-level REST client that connects to Elasticsearch
     * Then wraps it in the high-level ElasticsearchClient
     */
    @Bean
    public ElasticsearchClient elasticsearchClient(ObjectMapper objectMapper) {
        // Low-level HTTP client — just handles connection
        RestClient restClient = RestClient
                .builder(new HttpHost(host, port, "http"))
                .build();

        // Transport layer — handles serialization using our ObjectMapper
        ElasticsearchTransport transport = new RestClientTransport(
                restClient,
                new JacksonJsonpMapper(objectMapper)
        );

        // High-level client — what we use in our service classes
        return new ElasticsearchClient(transport);
    }
}