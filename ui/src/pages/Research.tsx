import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NewsFeed } from "@/pages/NewsFeed";
import { SystemsPanel } from "@/pages/SystemsPanel";

/**
 * Research.
 *
 * Everything about a system except running it: writing, backtesting,
 * optimising — plus the news that gives context to what the numbers did.
 * Execution lives in Trade, so the two are never confused.
 */
export function Research() {
  return (
    <div className="space-y-3 p-3 sm:p-4">
      <Tabs defaultValue="systems">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="systems">Systems</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
        </TabsList>

        <TabsContent value="systems" className="pt-3">
          {/* The systems panel manages its own full-height layout. */}
          <div className="h-[calc(100dvh-14rem)] min-h-[28rem] overflow-hidden rounded-lg border">
            <SystemsPanel />
          </div>
        </TabsContent>

        <TabsContent value="news" className="pt-3">
          <NewsFeed />
        </TabsContent>
      </Tabs>
    </div>
  );
}
