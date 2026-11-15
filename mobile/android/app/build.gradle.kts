import java.io.File
import java.io.FileInputStream
import java.util.Properties
import org.gradle.api.GradleException

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val signingPropertiesPath = providers.environmentVariable("BOOKLEDGER_SIGNING_PROPERTIES").orNull
val signingPropertiesFile = signingPropertiesPath?.let(::File)
val signingProperties = Properties()
if (signingPropertiesFile?.isFile == true) {
    FileInputStream(signingPropertiesFile).use(signingProperties::load)
}
val signingKeys = listOf("storeFile", "storePassword", "keyAlias", "keyPassword")
val missingSigningKeys = signingKeys.filter { signingProperties.getProperty(it).isNullOrBlank() }
val releaseBuildRequested = gradle.startParameter.taskNames.any { "release" in it.lowercase() }

if (releaseBuildRequested) {
    val propertiesFile = signingPropertiesFile
        ?: throw GradleException("Set BOOKLEDGER_SIGNING_PROPERTIES to an external release-signing properties file.")
    if (!propertiesFile.isAbsolute) {
        throw GradleException("BOOKLEDGER_SIGNING_PROPERTIES must be an absolute path.")
    }
    val canonicalPropertiesFile = propertiesFile.canonicalFile
    if (!canonicalPropertiesFile.isFile) {
        throw GradleException("The external release-signing properties file does not exist.")
    }
    if (canonicalPropertiesFile.toPath().startsWith(rootProject.projectDir.canonicalFile.toPath())) {
        throw GradleException("Release-signing properties must be stored outside the repository.")
    }
    if (missingSigningKeys.isNotEmpty()) {
        throw GradleException("The external release-signing properties file is missing: ${missingSigningKeys.joinToString()}.")
    }
    val configuredKeystore = File(signingProperties.getProperty("storeFile"))
    if (!configuredKeystore.isAbsolute) {
        throw GradleException("The configured release keystore path must be absolute.")
    }
    val keystore = configuredKeystore.canonicalFile
    if (!keystore.isFile) {
        throw GradleException("The configured release keystore does not exist.")
    }
    if (keystore.toPath().startsWith(rootProject.projectDir.canonicalFile.toPath())) {
        throw GradleException("The release keystore must be stored outside the repository.")
    }
}

val releaseSigningConfigured = signingPropertiesFile?.isFile == true && missingSigningKeys.isEmpty()

android {
    namespace = "com.bookledger.mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.bookledger.mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = File(signingProperties.getProperty("storeFile"))
                storePassword = signingProperties.getProperty("storePassword")
                keyAlias = signingProperties.getProperty("keyAlias")
                keyPassword = signingProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (releaseSigningConfigured) signingConfigs.getByName("release") else null
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
