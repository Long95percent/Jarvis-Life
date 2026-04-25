package com.shadowlink;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@MapperScan("com.shadowlink.**.mapper")
@ConfigurationPropertiesScan
@EnableAsync
public class ShadowLinkApplication {

    public static void main(String[] args) {
        SpringApplication.run(ShadowLinkApplication.class, args);
    }
}
