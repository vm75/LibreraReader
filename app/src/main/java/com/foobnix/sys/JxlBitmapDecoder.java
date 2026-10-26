package com.foobnix.sys;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import com.BaseExtractor;
import com.bumptech.glide.load.Options;
import com.bumptech.glide.load.ResourceDecoder;
import com.bumptech.glide.load.engine.Resource;
import com.bumptech.glide.load.engine.bitmap_recycle.BitmapPool;
import com.bumptech.glide.load.resource.bitmap.BitmapResource;

import org.ebookdroid.droids.mupdf.codec.MuPdfImage;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;

/** JXL catalogue covers, including Glide's stream and disk-cache paths. */
final class JxlBitmapDecoder implements ResourceDecoder<ByteBuffer, Bitmap> {
    private final BitmapPool pool;

    JxlBitmapDecoder(BitmapPool pool) {
        this.pool = pool;
    }

    @Override
    public boolean handles(ByteBuffer source, Options options) {
        ByteBuffer copy = source.duplicate();
        byte[] header = new byte[Math.min(12, copy.remaining())];
        copy.get(header);
        return MuPdfImage.isJxl(header);
    }

    @Override
    public Resource<Bitmap> decode(ByteBuffer source, int width, int height, Options options) throws IOException {
        ByteBuffer copy = source.duplicate();
        byte[] data = new byte[copy.remaining()];
        copy.get(data);
        return decode(data, width);
    }

    private Resource<Bitmap> decode(byte[] data, int width) throws IOException {
        try {
            byte[] png = MuPdfImage.decodeToPng(data, width > 0 ? width : Integer.MAX_VALUE);
            Bitmap bitmap = png == null ? null : BitmapFactory.decodeByteArray(png, 0, png.length);
            if (bitmap == null) {
                throw new IOException("Cannot decode JPEG XL image");
            }
            return BitmapResource.obtain(bitmap, pool);
        } catch (IllegalArgumentException e) {
            throw new IOException("Cannot decode JPEG XL image", e);
        }
    }

    static final class StreamDecoder implements ResourceDecoder<InputStream, Bitmap> {
        private final JxlBitmapDecoder decoder;

        StreamDecoder(BitmapPool pool) {
            decoder = new JxlBitmapDecoder(pool);
        }

        @Override
        public boolean handles(InputStream source, Options options) throws IOException {
            if (!source.markSupported()) {
                return false;
            }
            byte[] header = new byte[12];
            int count = 0;
            source.mark(header.length);
            try {
                while (count < header.length) {
                    int value = source.read();
                    if (value < 0) {
                        break;
                    }
                    header[count++] = (byte) value;
                }
                return MuPdfImage.isJxl(java.util.Arrays.copyOf(header, count));
            } finally {
                source.reset();
            }
        }

        @Override
        public Resource<Bitmap> decode(InputStream source, int width, int height, Options options) throws IOException {
            return decoder.decode(BaseExtractor.getEntryAsByte(source), width);
        }
    }
}
