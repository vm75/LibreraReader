import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.imageio.ImageIO;
import org.ebookdroid.droids.mupdf.codec.MuPdfImage;

/** Runs the production Java/JNI decoder on the host JVM, with real codec fixtures. */
public final class NativeImageSmoke {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static BufferedImage decode(Path directory, String name, int width) throws Exception {
        byte[] encoded = Files.readAllBytes(directory.resolve(name));
        byte[] png = MuPdfImage.decodeToPng(encoded, width);
        check(png != null, name + " returned no PNG");
        BufferedImage image = ImageIO.read(new ByteArrayInputStream(png));
        check(image != null, name + " returned an invalid PNG");
        return image;
    }

    public static void main(String[] args) throws Exception {
        Path directory = Path.of(args[0]);
        byte[] rgb = Files.readAllBytes(directory.resolve("rgb.jxl"));
        check(MuPdfImage.isJxl(rgb), "raw JPEG XL signature");
        check(MuPdfImage.isJxl(Files.readAllBytes(directory.resolve("rgba.jxl"))), "container JPEG XL signature");
        check(MuPdfImage.isWebp(Files.readAllBytes(directory.resolve("rgb.webp"))), "WebP signature");
        check(!MuPdfImage.isJxl(new byte[]{0, 0, 0, 12}), "truncated JXL container");
        check(!MuPdfImage.isWebp(new byte[]{'R', 'I', 'F', 'F'}), "truncated RIFF");
        check(MuPdfImage.decodeToPng(new byte[]{1, 2}, 10) == null, "unsupported format");
        if (System.getProperty("test.flavor", "fdroid").endsWith("JS")) {
            check(MuPdfImage.decodeToPng(rgb, 10) == null, "JS variant must not load MuPDF");
            System.out.println("MuPDF-free image guard passed");
            return;
        }
        for (String extension : new String[]{"webp", "jxl"}) {
            BufferedImage image = decode(directory, "rgb." + extension, 100);
            check(image.getWidth() == 2 && image.getHeight() == 2, extension + " dimensions/upscaling");
            check((image.getRGB(0, 0) & 0xffffff) == 0xff0000, extension + " red pixel");
            BufferedImage small = decode(directory, "rgb." + extension, 1);
            check(small.getWidth() == 1 && small.getHeight() == 1, extension + " thumbnail scaling");
            BufferedImage alpha = decode(directory, "rgba." + extension, 100);
            check((alpha.getRGB(1, 0) >>> 24) == 128, extension + " partial alpha");
            check((alpha.getRGB(0, 1) >>> 24) == 0, extension + " transparent pixel");
        }
        BufferedImage rotated = decode(directory, "oriented.jxl", 100);
        check(rotated.getWidth() == 2 && rotated.getHeight() == 3, "JPEG XL orientation");
        BufferedImage gray = decode(directory, "gray.jxl", 100);
        check(gray.getWidth() == 2 && gray.getHeight() == 2, "16-bit grayscale JPEG XL");
        for (int i = 0; i < 10; ++i) {
            boolean rejected = false;
            try {
                MuPdfImage.decodeToPng(new byte[]{(byte)255, 10}, 10);
            } catch (IllegalArgumentException expected) {
                rejected = true;
            }
            check(rejected, "malformed image must throw a Java exception");
            decode(directory, "rgb.jxl", 10);
        }
        System.out.println("Production WebP/JXL JNI image decoding passed");
    }
}
