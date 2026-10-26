#include <jni.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include "mupdf/fitz.h"

/* Covers and image previews need an Android-decodable stream as well as pages. */
JNIEXPORT jbyteArray JNICALL
Java_org_ebookdroid_droids_mupdf_codec_MuPdfImage_nativeDecodeToPng(
    JNIEnv *env, jclass clazz, jbyteArray encoded, jint requested_width)
{
    fz_context *ctx;
    fz_buffer *input = NULL, *png = NULL;
    fz_stream *stream = NULL;
    fz_document *doc = NULL;
    fz_page *page = NULL;
    fz_pixmap *pixmap = NULL;
    jbyte *bytes;
    jbyteArray result = NULL;
    char error[256] = {0};
    int failed = 0;
    jsize length;

    if (!encoded || requested_width <= 0)
        return NULL;
    length = (*env)->GetArrayLength(env, encoded);
    bytes = (*env)->GetByteArrayElements(env, encoded, NULL);
    if (!bytes)
        return NULL;
    ctx = fz_new_context(NULL, NULL, FZ_STORE_DEFAULT);
    if (!ctx)
    {
        (*env)->ReleaseByteArrayElements(env, encoded, bytes, JNI_ABORT);
        (*env)->ThrowNew(env, (*env)->FindClass(env, "java/lang/OutOfMemoryError"), "MuPDF image context");
        return NULL;
    }

    fz_var(input);
    fz_var(png);
    fz_var(stream);
    fz_var(doc);
    fz_var(page);
    fz_var(pixmap);
    fz_var(result);
    fz_var(failed);
    fz_try(ctx)
    {
        fz_rect bounds;
        float width, scale;
        unsigned char *data;
        size_t size;

        fz_register_document_handlers(ctx);
        input = fz_new_buffer_from_shared_data(ctx, (unsigned char *)bytes, length);
        stream = fz_open_buffer(ctx, input);
        doc = fz_open_document_with_stream(ctx, "image", stream);
        page = fz_load_page(ctx, doc, 0);
        bounds = fz_bound_page(ctx, page);
        width = bounds.x1 - bounds.x0;
        if (!isfinite(width) || width <= 0)
            fz_throw(ctx, FZ_ERROR_FORMAT, "invalid image dimensions");
        scale = fz_min(1, requested_width / width);
        pixmap = fz_new_pixmap_from_page(ctx, page, fz_scale(scale, scale), fz_device_rgb(ctx), 1);
        png = fz_new_buffer_from_pixmap_as_png(ctx, pixmap, fz_default_color_params);
        size = fz_buffer_storage(ctx, png, &data);
        if (size > INT_MAX)
            fz_throw(ctx, FZ_ERROR_LIMIT, "decoded image is too large");
        result = (*env)->NewByteArray(env, (jsize)size);
        if (result)
            (*env)->SetByteArrayRegion(env, result, 0, (jsize)size, (jbyte *)data);
    }
    fz_always(ctx)
    {
        fz_drop_buffer(ctx, png);
        fz_drop_pixmap(ctx, pixmap);
        fz_drop_page(ctx, page);
        fz_drop_document(ctx, doc);
        fz_drop_stream(ctx, stream);
        fz_drop_buffer(ctx, input);
    }
    fz_catch(ctx)
    {
        failed = 1;
        snprintf(error, sizeof error, "%s", fz_caught_message(ctx));
        fz_ignore_error(ctx);
    }
    fz_drop_context(ctx);
    (*env)->ReleaseByteArrayElements(env, encoded, bytes, JNI_ABORT);
    if (failed && !(*env)->ExceptionCheck(env))
        (*env)->ThrowNew(env, (*env)->FindClass(env, "java/lang/IllegalArgumentException"), error);
    return result;
}
