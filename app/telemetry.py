from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_telemetry(service_name: str):
    """
    Khởi tạo OpenTelemetry Provider và ghi đè Provider mặc định toàn cầu.
    Thiết lập xuất log ra màn hình Console để tiện debug và trực quan hóa trace_id.
    """
    # 1. Định nghĩa Tên Dịch Vụ
    resource = Resource.create({"service.name": service_name})
    
    # 2. Tạo TracerProvider mới
    provider = TracerProvider(resource=resource)
    
    # 3. Thêm Console Exporter: Mỗi khi một span (vùng mã) kết thúc, nó in ra console
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    
    # 4. Gán Provider này làm mặc định cho toàn bộ thư viện OpenTelemetry chạy trong luồng
    trace.set_tracer_provider(provider)
    
    return provider
