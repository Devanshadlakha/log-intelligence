package com.logintel.consumer;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch.core.IndexRequest;
import co.elastic.clients.elasticsearch.core.IndexResponse;
import com.logintel.model.LogEntry;
import com.logintel.websocket.LogWebSocketService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Service;

/**
 * Listens to the "app-logs" Kafka topic.
 * For every log message received, it saves it to Elasticsearch.
 *
 * Flow: Kafka → this consumer → Elasticsearch index "logs"
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LogConsumerService {

    private static final String INDEX_NAME = "logs";

    private final ElasticsearchClient elasticsearchClient;
    private final LogWebSocketService webSocketService;

    /**
     * @KafkaListener — Spring automatically calls this method
     * whenever a new message arrives on the "app-logs" topic.
     *
     * groupId = "log-consumer-group" — allows multiple consumers
     * to share the load (we only have one here, but good practice)
     */
    @KafkaListener(
            topics = "app-logs",
            groupId = "log-consumer-group",
            containerFactory = "kafkaListenerContainerFactory"
    )
    public void consumeLog(
            LogEntry logEntry,
            @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
            @Header(KafkaHeaders.OFFSET) long offset
    ) {
        log.debug("Received log from Kafka → partition: {}, offset: {}, service: {}",
                partition, offset, logEntry.getService());

        indexToElasticsearch(logEntry);

        // Broadcast to WebSocket clients for real-time dashboard updates
        webSocketService.broadcastLog(logEntry);
    }

    /**
     * Saves a single LogEntry to Elasticsearch with retry.
     * The document ID is the log's UUID — prevents duplicates on retry.
     *
     * Retry strategy: 3 attempts with 1-second delay between each.
     * Using the log's UUID as document ID means retries are idempotent —
     * if the same log is indexed twice, Elasticsearch just overwrites it.
     */
    private void indexToElasticsearch(LogEntry logEntry) {
        int maxRetries = 3;

        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                IndexRequest<LogEntry> request = IndexRequest.of(i -> i
                        .index(INDEX_NAME)
                        .id(logEntry.getId())
                        .document(logEntry)
                );

                IndexResponse response = elasticsearchClient.index(request);

                log.debug("Indexed log to Elasticsearch → id: {}, result: {}",
                        response.id(), response.result().jsonValue());
                return; // success — exit retry loop

            } catch (Exception e) {
                log.warn("ES index failed (attempt {}/{}) → id: {}, error: {}",
                        attempt, maxRetries, logEntry.getId(), e.getMessage());

                if (attempt < maxRetries) {
                    try {
                        Thread.sleep(1000L * attempt); // 1s, 2s backoff
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                } else {
                    log.error("All ES retries exhausted → id: {}, dropping log",
                            logEntry.getId());
                }
            }
        }
    }
}