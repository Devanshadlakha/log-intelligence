package com.logintel.config;

import com.logintel.model.LogEntry;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.support.serializer.JsonDeserializer;
import org.springframework.util.backoff.FixedBackOff;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka configuration — sets up:
 * 1. Consumer (Kafka → Spring Boot for indexing to Elasticsearch)
 * 2. Topic creation
 */
@Configuration
public class KafkaConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    // ─── Topic ────────────────────────────────────────────────
    // Creates "app-logs" topic automatically if it doesn't exist
    @Bean
    public NewTopic logTopic() {
        return new NewTopic("app-logs", 1, (short) 1);
        // args: topic name, partitions, replication factor
    }

    // ─── Consumer Config ──────────────────────────────────────
    // Tells Kafka how to deserialize JSON bytes back to LogEntry
    @Bean
    public ConsumerFactory<String, LogEntry> consumerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(ConsumerConfig.GROUP_ID_CONFIG, "log-consumer-group");
        config.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        config.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JsonDeserializer.class);
        // Trust our LogEntry class during deserialization
        config.put(JsonDeserializer.TRUSTED_PACKAGES, "com.logintel.model");
        config.put(JsonDeserializer.VALUE_DEFAULT_TYPE, LogEntry.class.getName());
        // Read from beginning if no offset exists
        config.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        return new DefaultKafkaConsumerFactory<>(config);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, LogEntry> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, LogEntry> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());

        // Retry failed messages 3 times with 2-second delay between attempts.
        // After 3 failures, the message is skipped (logged as error) so it
        // doesn't block consumption of subsequent messages.
        factory.setCommonErrorHandler(
                new DefaultErrorHandler(new FixedBackOff(2000L, 3L))
        );

        return factory;
    }
}