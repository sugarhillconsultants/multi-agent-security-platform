/*
 * mcp_servers/AccumuloReader.java
 *
 * Reads a specific row+column-family from Project 6 (Secure Data
 * Fusion Platform)'s real Accumulo table — the read-side counterpart
 * to that project's AccumuloBulkWriter.java, using the same real,
 * current, documented AccumuloClient API (Accumulo.newClient()...
 * build()), not the deprecated 1.x pattern.
 *
 * DELIBERATE DESIGN NOTE: this program does NOT implement any access
 * control decision itself. By the time fusion_server.py invokes this,
 * agents/authorization.py has ALREADY decided — per field, before
 * dispatch — that the calling session is cleared to see this specific
 * row+family. This program's only job is to fetch already-authorized
 * data using a full-access service credential (root); it is not a
 * second enforcement point, and shouldn't be treated as one. See
 * docs/incidents.md.
 *
 * NOT YET COMPILED OR RUN — written against Accumulo 2.1.2's
 * documented Scanner API, the same way AccumuloBulkWriter.java was
 * before its first real compile surfaced (and fixed) a genuine
 * encoding issue. Expect the same here.
 */

import org.apache.accumulo.core.client.Accumulo;
import org.apache.accumulo.core.client.AccumuloClient;
import org.apache.accumulo.core.client.Scanner;
import org.apache.accumulo.core.data.Key;
import org.apache.accumulo.core.data.Range;
import org.apache.accumulo.core.data.Value;
import org.apache.accumulo.core.security.Authorizations;
import org.apache.hadoop.io.Text;

import java.util.Map;

public class AccumuloReader {

    public static void main(String[] args) throws Exception {
        if (args.length < 6) {
            System.err.println("Usage: AccumuloReader <row> <columnFamily> <tableName> "
                + "<instanceName> <zookeepers> <password>");
            System.exit(1);
        }

        String row = args[0];
        String columnFamily = args[1];
        String tableName = args[2];
        String instanceName = args[3];
        String zookeepers = args[4];
        String password = args[5];
        String username = "root"; // matches this project's docker-compose ACCUMULO_ROOT_PASSWORD setup

        AccumuloClient client = Accumulo.newClient()
                .to(instanceName, zookeepers)
                .as(username, password)
                .build();

        // Full authorizations — this program fetches already-authorized
        // data, it does not decide authorization itself. See file header.
        Authorizations fullAuths = new Authorizations("U", "S", "REL_TO_FVEY", "TS", "SI", "NOFORN");

        Scanner scanner = client.createScanner(tableName, fullAuths);
        scanner.setRange(Range.exact(new Text(row)));
        scanner.fetchColumnFamily(new Text(columnFamily));

        boolean foundAny = false;
        for (Map.Entry<Key, Value> entry : scanner) {
            foundAny = true;
            Key key = entry.getKey();
            Value value = entry.getValue();
            // Tab-separated, one line per column qualifier found:
            // row \t columnFamily \t columnQualifier \t visibility \t value
            System.out.println(
                key.getRow() + "\t" +
                key.getColumnFamily() + "\t" +
                key.getColumnQualifier() + "\t" +
                key.getColumnVisibility() + "\t" +
                value.toString()
            );
        }

        scanner.close();
        client.close();

        if (!foundAny) {
            System.err.println("No data found for row=" + row + " columnFamily=" + columnFamily);
        }
    }
}
